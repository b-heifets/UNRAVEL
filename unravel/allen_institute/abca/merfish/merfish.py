#!/usr/bin/env python3

"""
Use ``abca_merfish`` or ``mf`` from UNRAVEL to plot MERFISH data from the Allen Brain Cell Atlas (ABCA). This script has several useful functions for ABCA data exploration.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/merfish_ccf_registration_tutorial.html#read-in-section-reconstructed-and-ccf-coordinates-for-all-cells
    - The slice index ranges from 05 to 67.
    - Missing slices include: 07 20 21 22 23 34 41 63 65.

Usage for gene expression:
--------------------------
    abca_merfish -b path/to/base_dir -s slice -g gene

Usage for color:
----------------
    abca_merfish -b path/to/base_dir -s slice -c color
"""

import anndata
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import SimpleITK as sitk
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-s', '--slice', help='The brain slice to view (e.g., 40)', type=int, required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-g', '--gene', help='Gene to plot.', action=SM)
    opts.add_argument('-c', '--color', help='Color to plot (e.g., parcellation_substructure_color or neurotransmitter_color)', action=SM)
    opts.add_argument('-im', '--imputed', help='Use imputed expression data. Default: False', action='store_true', default=False)
    opts.add_argument('-o', '--output', help='Path to save the plot rather than showing it with Matplotlib (end with .png)', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Make base cwd by default. Consider intergrating with the cache tool from Allen. 
# TODO: Offload the lists of genes to CSVs
# TODO: Offload common functions to allen_utils.py
# TODO: Add option to download the data if not present
# TODO: Rename functions from cluster details to cell details etc

def load_cell_metadata(download_base):
    """
    Load the cell metadata DataFrame from the MERFISH data (using cell_label as the index).

    Parameters:
    -----------
    download_base : Path
        The root directory of the MERFISH data or the path to the cell metadata.

    Returns:
    --------
    cell_df : pd.DataFrame
        The cell metadata. Columns: 'brain_section_label', 'cluster_alias', 'average_correlation_score', 'feature_matrix_label', 'donor_label', 'donor_genotype', 'donor_sex', 'x_section', 'y_section', 'z_section'

    """
    if Path(download_base).is_file():
        cell_metadata_path = download_base
    else:
        cell_metadata_path = download_base / 'metadata/MERFISH-C57BL6J-638850/20231215/cell_metadata.csv'
    print(f"\n    Loading cell metadata from {cell_metadata_path}\n")
    cell_df = pd.read_csv(cell_metadata_path, dtype={'cell_label': str})
    cell_df.rename(columns={'x': 'x_section',
                        'y': 'y_section',
                        'z': 'z_section'},
                inplace=True)
    cell_df.set_index('cell_label', inplace=True)
    return cell_df

def join_reconstructed_coords(cell_df, download_base):
    """
    Join the cell metadata with the reconstructed coordinates (using cell_label).

    Parameters:
    -----------
    cell_df : pd.DataFrame
        The cell metadata.
    download_base : Path
        The root directory of the MERFISH data.

    Returns:
    --------
    cell_joined : pd.DataFrame
        The cell metadata joined with the reconstructed coordinates. Added columns: 'x_reconstructed', 'y_reconstructed', 'z_reconstructed', 'parcellation_index'

    """
    reconstructed_coords_path = download_base / 'metadata/MERFISH-C57BL6J-638850-CCF/20231215/reconstructed_coordinates.csv'
    print(f"\n    Adding reconstructed coordinates from {reconstructed_coords_path}\n")
    reconstructed_coords_df = pd.read_csv(reconstructed_coords_path, dtype={'cell_label': str})
    reconstructed_coords_df.rename(columns={'x': 'x_reconstructed', 'y': 'y_reconstructed', 'z': 'z_reconstructed'}, inplace=True)
    reconstructed_coords_df.set_index('cell_label', inplace=True)
    cell_df_joined = cell_df.join(reconstructed_coords_df, how='inner')
    return cell_df_joined

def join_cluster_details(cell_df_joined, download_base, species='mouse'):
    """
    Join the cell metadata DataFrame with the cluster details (using 'cluster_alias').

    Parameters:
    -----------
    cell_df_joined : pd.DataFrame
        The cell metadata DataFrame [joined with other metadata].
    download_base : Path
        The root directory of the Allen Brain Cell Atlas data.

    Returns:
    --------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the cluster details. 
        Added mouse columns: 'neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'
        Added human columns: 'neurotransmitter', 'supercluster', 'cluster', 'subcluster'
    """
    if species == 'mouse':
        cluster_details_path = download_base / 'metadata/WMB-taxonomy/20231215/views/cluster_to_cluster_annotation_membership_pivoted.csv'
    elif species == 'human':
        cluster_details_path = Path(__file__).parent.parent.parent.parent.parent / 'unravel' / 'core' / 'csvs' / 'ABCA' / 'WHB_cluster_to_cluster_annotation_membership_pivoted.csv'
    else:
        raise ValueError(f"Species '{species}' not supported. Use 'mouse' or 'human'.")
    
    print(f"\n    Adding cluster details from {cluster_details_path}\n")
    cluster_details = pd.read_csv(cluster_details_path)
    cluster_details.set_index('cluster_alias', inplace=True)
    cell_df_joined = cell_df_joined.join(cluster_details, on='cluster_alias')
    return cell_df_joined

def join_cluster_colors(cell_df_joined, download_base, species='mouse'):
    """
    Join the cell metadata DataFrame with the cluster colors (using 'cluster_alias').

    Parameters:
    -----------
    cell_df_joined : pd.DataFrame
        The cell metadata DataFrame [joined with other metadata].
    download_base : Path
        The root directory of the Allen Brain Cell Atlas data.

    Returns:
    --------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the cluster colors. 
        Added mouse columns: 'neurotransmitter_color', 'class_color', 'subclass_color', 'supertype_color', 'cluster_color'
        Added human columns: 'neurotransmitter_color', 'supercluster_color', 'cluster_color', 'subcluster_color'
    
    """
    if species == 'mouse':
        cluster_colors_path = download_base / 'metadata/WMB-taxonomy/20231215/views/cluster_to_cluster_annotation_membership_color.csv'
    elif species == 'human':
        cluster_colors_path = Path(__file__).parent.parent.parent.parent.parent / 'unravel' / 'core' / 'csvs' / 'ABCA' / 'WHB_cluster_to_cluster_annotation_membership_color.csv'
    print(f"\n    Adding cluster colors from {cluster_colors_path}\n")
    cluster_colors = pd.read_csv(cluster_colors_path)
    cluster_colors.set_index('cluster_alias', inplace=True)
    cell_df_joined = cell_df_joined.join(cluster_colors, on='cluster_alias')
    return cell_df_joined

def join_parcellation_annotation(cell_df_joined, download_base):
    """
    Join the cell metadata DataFrame with the parcellation annotation (using parcellation_index).

    Parameters:
    -----------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the cluster colors.
    download_base : Path
        The root directory of the MERFISH data.

    Returns:
    --------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the parcellation annotation. Added columns: 'parcellation_organ', 'parcellation_category', 'parcellation_division', 'parcellation_structure', 'parcellation_substructure'
    
    """
    parcellation_annotation_path = download_base / 'metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_acronym.csv'
    print(f"\n    Adding parcellation annotation from {parcellation_annotation_path}\n")
    parcellation_annotation = pd.read_csv(parcellation_annotation_path)
    parcellation_annotation.set_index('parcellation_index', inplace=True)
    parcellation_annotation.columns = ['parcellation_%s'% x for x in  parcellation_annotation.columns]
    cell_df_joined = cell_df_joined.join(parcellation_annotation, on='parcellation_index')
    return cell_df_joined

def join_parcellation_color(cell_df_joined, download_base):
    """
    Join the cell metadata DataFrame with the parcellation color (using parcellation_index).

    Parameters:
    -----------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the parcellation annotation.
    download_base : Path
        The root directory of the MERFISH data.

    Returns:
    --------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the parcellation color. Added columns: 'parcellation_organ_color', 'parcellation_category_color', 'parcellation_division_color', 'parcellation_structure_color', 'parcellation_substructure_color'
    
    """
    parcellation_color_path = download_base / 'metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_color.csv'
    print(f"\n    Adding parcellation color from {parcellation_color_path}\n")
    parcellation_color = pd.read_csv(parcellation_color_path)
    parcellation_color.set_index('parcellation_index', inplace=True)
    parcellation_color.columns = ['parcellation_%s'% x for x in  parcellation_color.columns]
    cell_df_joined = cell_df_joined.join(parcellation_color, on='parcellation_index')
    return cell_df_joined

def filter_brain_section(cell_df, slice_index):
    """
    Filter the cell metadata DataFrame for a specific brain section (using brain_section_label).
    
    Parameters:
    -----------
    cell_df : pd.DataFrame
        The cell metadata.
    slice_index : int
        The index of the brain section to filter for.
    
    Returns:
    --------
    section : pd.DataFrame
        The cell metadata for the specified brain section.
"""
    brain_section = f'C57BL6J-638850.{slice_index}'
    pred = (cell_df['brain_section_label'] == brain_section)
    section = cell_df[pred]
    return section

def load_region_boundaries(download_base):
    """
    Load the region boundaries from the MERFISH data.

    Parameters:
    -----------
    download_base : Path
        The root directory of the MERFISH data.

    Returns:
    --------
    annotation_boundary_array : np.ndarray
        The region boundaries.
    extent : tuple
        The extent of the image in mm coordinates for plotting with matplotlib.
    """
    annotation_boundary_image_path = download_base / 'image_volumes/MERFISH-C57BL6J-638850-CCF/20230630/resampled_annotation_boundary.nii.gz'
    print(f"\n    Loading annotation boundary image from {annotation_boundary_image_path}\n")
    annotation_boundary_image = sitk.ReadImage(annotation_boundary_image_path)
    annotation_boundary_array = sitk.GetArrayViewFromImage(annotation_boundary_image)

    # Compute the extent the image in mm coordinates for plotting
    size = annotation_boundary_image.GetSize()
    spacing = annotation_boundary_image.GetSpacing()
    extent = (-0.5 * spacing[0], (size[0]-0.5) * spacing[0], (size[1]-0.5) * spacing[1], -0.5 * spacing[1])

    return annotation_boundary_array, extent

def load_expression_data(download_base, gene, imputed=False):
    """
    Load the expression data from the MERFISH data.

    Parameters:
    -----------
    download_base : Path
        The root directory of the MERFISH data.

    Returns:
    --------
    adata : anndata.AnnData object with n_obs x n_vars = 4334174 x 550
        The expression data. obs: 'brain_section_label', var: 'gene_symbol', 'transcript_identifier', uns: 'accessed_on', 'src'
    """
    genes_in_merfish = []
    genes_in_imputed_merfish = []
    if not imputed:
        genes_in_merfish = genes_in_merfish_data()
        if gene not in genes_in_merfish:
            print(f"    Gene [yellow]{gene}[/] not found in MERFISH data, using imputed data.")
            genes_in_imputed_merfish = genes_in_imputed_merfish_data()

            if gene not in genes_in_imputed_merfish:
                print(f"    Gene [yellow]{gene}[/] not found in imputed MERFISH data.")
                import sys ; sys.exit()
    else:
        genes_in_imputed_merfish = genes_in_imputed_merfish_data()
        if gene not in genes_in_imputed_merfish:
            print(f"    Gene [yellow]{gene}[/] not found in imputed MERFISH data.")
            import sys ; sys.exit()

    if genes_in_merfish:
        expression_path = download_base / 'expression_matrices/MERFISH-C57BL6J-638850/20230830/C57BL6J-638850-log2.h5ad'
    else:
        expression_path = download_base / 'expression_matrices/MERFISH-C57BL6J-638850-imputed/20240831/C57BL6J-638850-imputed-log2.h5ad'

    print(f"\n    Loading expression data from {expression_path}\n")
    adata = anndata.read_h5ad(expression_path, backed='r')
    return adata

def filter_expression_data(adata, gene):
    """
    Filter the expression data for a specific gene.

    Parameters:
    -----------
    adata : anndata.AnnData
        The expression data.
    gene : str
        The gene to filter for.

    Returns:
    --------
    asubset : anndata.AnnData
        The expression data subset for the specified gene. Columns: 'gene_symbol'
    gf : pd.DataFrame
        The gene metadata for the specified gene. Columns: 'gene_symbol', 'transcript_identifier'
    """
    print(f"\n    Filtering expression data for gene {gene}\n")
    genes = [gene]
    pred = [x in genes for x in adata.var.gene_symbol]  # Filter for the gene of interest
    gene_filtered = adata.var[pred]  # Get the gene metadata for the gene of interest
    asubset = adata[:, gene_filtered.index].to_memory()  # Get the expression data for the gene of interest
    pred = [x in genes for x in asubset.var.gene_symbol]  # Filter expression data for the gene of interest
    gf = asubset.var[pred]  # Get the gene metadata for the gene of interest

    return asubset, gf

def create_expression_dataframe(ad, gf, section):
    """
    Extracts expression data for a specific gene by its symbol and returns a DataFrame.
    
    Parameters:
    -----------
    ad : anndata.AnnData
        An anndata object containing the expression data. Columns: 'gene_symbol'

    gf : pd.DataFrame
        A DataFrame containing the gene metadata. Columns: 'gene_symbol', 'transcript_identifier'

    section : pd.DataFrame
        A DataFrame containing the cell metadata for a specific brain section. Columns: 'brain_section_label', 'cluster_alias', ...

    Returns:
    --------
    joined : pd.DataFrame
        A DataFrame containing the expression data for the gene in the specified brain section.
    """
    gdata = ad[:, gf.index].to_df()  # Extract expression data for the gene
    gdata.columns = gf.gene_symbol  # Set the column names to the gene symbols
    joined = section.join(gdata)  # Join the cell metadata with the expression data
    return joined

def genes_in_merfish_data():
    genes = [
    'Prkcq', 'Otp', 'C230014O12Rik', 'Fstl5', 'Tcf7l2', 'Aqp4', 'Epha4', 'Npnt',
    'Lhfp', 'Wnt7b', 'Sulf2', 'Sox6', 'C030029H02Rik', 'Fgf10', 'Igf2', 'Calcb',
    'Sox10', 'Ltbp1', 'Chrm2', 'Baiap3', 'Col11a1', 'Clic6', 'Ctss', 'Vegfc',
    'Zic1', 'Dgkk', 'Pdgfd', 'Man1a', 'Sntg2', 'Arhgap28', 'Tacr3', 'Gpr83',
    'Egln3', 'Spon1', 'Oxtr', 'Crh', 'Sema5a', 'Nptx2', 'Mmel1', 'Col8a1',
    'Egflam', 'Col23a1', 'Gli3', 'Bcl11a', 'Pde11a', 'Sv2c', 'Slit2', 'Kcnj8',
    'Rspo2', 'Fam163a', 'Tal1', 'Trhde', 'Syt2', 'Grp', 'Lhx2', 'Cited1',
    'Gpr101', 'G630016G05Rik', 'Chrnb3', 'Col5a1', 'Calb1', 'Hspg2', 'Dock5',
    'Rbp4', 'Slc7a10', 'Serpine2', 'Foxa1', 'Cdh20', 'Mpped2', 'Lypd1', 'Tafa2',
    'Scn4b', 'Lama1', 'Fli1', 'Hoxb5', 'Fibcd1', 'Cd36', 'Ngb', 'Tac2', 'Mog',
    'Ramp3', 'Scgn', 'Slc6a5', 'Ror1', 'Galnt18', 'Nxph1', 'Aqp1', 'Slc6a3',
    'Vit', 'Pax7', 'Tent5a', 'Tbcc', 'Piezo2', 'Zfpm2', 'C1ql3', 'A630012P03Rik',
    'Tnnt1', 'Syt17', 'Sp9', 'Grem1', 'Bnc2', 'Pax6', 'Tmem132c', 'Gfra1',
    'Prkg2', 'Ptger3', 'Cyp26b1', 'St3gal1', 'Vip', 'Slc30a3', 'Tll1', 'Tafa1',
    'Chrm3', 'Eomes', 'Drd2', 'Npsr1', 'Adra1a', 'Grik3', 'Vwa5b1', 'Pitx2',
    'Kcnk9', 'Serpinb8', 'Grin2c', 'Bmpr1b', 'Lgr6', 'Agt', 'Pcp4l1', 'Mrpl16',
    'Zfp521', 'Ust', 'Cd24a', 'Kcnab3', 'Elfn1', 'Epha3', 'Fxyd6', 'Gad2',
    'Slc7a11', 'Tmem215', 'Syndig1l', 'Kcnj5', 'Penk', 'Kctd8', 'Prkd1', 'Lhfpl5',
    'Ccn4', 'Cartpt', 'Fbn2', 'Sema3c', 'Tgfbr2', 'Parm1', 'Egr2', 'Arhgap15',
    'Marcksl1', 'Wls', 'Sema3e', 'Gpx3', 'Nr2f1', 'Samd5', 'Nxph2', 'Lypd6',
    'Kcnmb2', 'Fign', 'Glis3', 'Nkx2-1', 'Lhx8', 'Gm30564', 'Slc6a4', 'Rwdd2a',
    'Chn2', 'Klhl14', 'Prrxl1', 'Hcrtr2', 'Syt10', 'Irs4', 'Onecut2', 'Igfbp2',
    'Ptprm', 'Pparg', 'Stxbp6', 'Rorb', 'Grm3', 'Gsta4', 'Slc32a1', 'Ldb2',
    'Hopx', 'Cbln2', 'Lrp4', 'Moxd1', 'Sp8', 'Tox', 'Gpr88', 'Kit', 'Pax5',
    'Cnr1', 'Stac', 'Tfap2d', 'Bmp4', 'Dach1', 'Nrp1', 'Eya2', 'Cidea', 'Ebf1',
    'Phox2b', 'Ptk2b', 'Kazald1', 'Rspo1', 'Cdh6', 'Necab1', 'Il31ra', 'Oprd1',
    'Gli2', 'Megf11', 'Otof', 'Pappa', 'Ctxn3', 'Rprm', 'Gata3', 'Shroom3',
    'Egfem1', 'Pif1', 'Nwd2', 'Edaradd', 'Htr3a', 'Drd3', 'Galnt14', 'Npbwr1',
    'Calcr', 'Barhl1', '4930509J09Rik', 'Lncenc1', 'Trpc7', 'Synpr', 'Prom1',
    'Osr1', 'Rxfp3', 'Calb2', 'Nfib', 'Adamts9', 'Slc1a3', 'Fras1', 'Tmie',
    'Kcng2', 'Spock3', 'Zfhx4', 'St6galnac5', 'Kcng1', 'Dcn', 'Opalin', 'Tox3',
    'Ccdc3', 'Pax8', 'Cgnl1', 'Cldn5', 'Svep1', 'Ighm', 'Mkx', 'Shox2',
    'Bcl11b', 'Creb3l1', 'Klk6', 'Lpl', 'Angpt1', 'Mcm6', 'Fosl2', 'Htr2a',
    'Drd5', 'Hoxb8', 'Vwc2', 'Casr', 'Gpc3', 'Hmcn1', 'Hs3st2', 'Plpp4',
    'Abcc9', 'Kitl', 'Fbln2', 'Adamtsl1', 'Ung', 'Sla', 'B230323A14Rik', 'Kcns3',
    'Cdkn1a', 'Tfap2b', 'Igfbpl1', 'Mctp2', 'Dmbx1', 'Ankfn1', 'Otx2', 'Grpr',
    'Foxb1', 'D130079A08Rik', 'Syt6', 'Cpne8', 'Cxcl14', 'Gfap', 'Ccbe1',
    'Pvalb', 'Col27a1', 'Adamts19', 'Cacng3', 'A830036E02Rik', 'Zeb2', 'Gpr39',
    'Pou6f2', 'Chst9', 'Cntn6', 'Arhgap36', 'Nr4a3', 'Onecut3', 'Cbln4', 'Ccn3',
    'Glra2', 'Tnc', 'Fyb', 'Htr7', 'Mab21l2', 'C1ql1', 'Ccnd2', 'Cd34', 'Chodl',
    'Cd247', 'Bmp3', 'Lmo1', 'Esyt3', 'Ckap2l', 'Lamp5', 'Scn5a', 'Lancl3',
    'Pdzrn3', 'Barhl2', 'Hs3st3b1', 'Arhgap25', 'Car4', 'Igsf1', 'Tbx3',
    'Pou4f1', 'Corin', 'Htr1b', 'Crhbp', 'Qpct', 'Cnih3', 'Ttc29', 'Gpr139',
    'Ntng1', 'Grik1', 'St18', 'Dscaml1', 'Prok2', 'Th', 'Cntnap3', 'Igfbp6',
    'Rgs4', 'Gja1', 'Nos1', 'Igfbp4', 'Nrn1', 'Foxo1', 'Zbtb16', 'Adra1b',
    'Unc13c', 'Oprk1', '2900052N01Rik', 'Sorcs3', 'Ebf3', 'Abi3bp', 'Acta2',
    'Adcyap1', 'Medag', 'Kif11', 'Sv2b', 'Drd1', 'Rasgrp1', 'Unc5d', 'Slc17a7',
    'Hs3st4', 'Glra3', 'Lhx1', 'Aqp6', 'Nr4a2', 'Nr2f2', 'Trhr', 'Scn7a',
    'Ppp1r17', 'Gpr149', 'Galr1', 'Slit3', 'Ethe1', 'Gda', 'Nxph4', 'Kcnip1',
    'Mecom', 'Met', 'Prlr', 'Myo5b', 'Cbln1', 'Hgf', 'Adgrv1', 'Gal', 'Npy2r',
    'Spin2c', 'Tafa4', 'Ddc', 'D130009I18Rik', '9330158H04Rik', 'Grm1', 'Foxa2',
    'Cpa6', 'Lmo3', 'Isl1', 'Slc17a6', 'Igf1', 'Emx2', 'Adcy2', 'Sox5', 'Ndnf',
    'Sox2', 'Lsp1', 'Rgs6', 'Col18a1', 'Six3', 'Dlk1', 'Zic4', 'Slc38a1',
    'Vcan', 'Nts', 'Whrn', 'Irx2', 'Popdc3', 'Grm8', 'Adamts2', 'Ecel1', 'Evx2',
    'Slc17a8', 'Smoc2', 'Hdc', 'Crym', 'Zic5', 'Pde3a', 'Dmrt2', 'Dsg2',
    'Agtr1a', 'Chat', 'Kl', 'Htr1d', 'Slc5a7', 'Pde1a', 'Tshz2', 'Skor1',
    'Apela', 'Tcerg1l', 'Vsx2', 'Tacr1', 'Pnoc', 'Dbh', 'Col24a1', 'Pou3f1',
    'Qrfpr', 'Dio3', 'Rmst', 'Lhx9', 'Gabrq', 'Ntn1', 'Shisa6', 'Ramp1', 'Nhlh2',
    'Pou3f3', 'Lpar1', 'Dchs2', 'Hoxb3', 'Ebf2', 'Cdh9', 'Rxfp1', 'Syndig1',
    'Vwc2l', 'Maf', 'Osbpl3', 'Pth2r', 'Zfp536', 'Rab3b', 'Wif1', 'Clic5',
    'Pdyn', 'Hpgd', 'Kcnh8', 'Cftr', 'Gpr4', 'Nkx2-4', 'En1', 'Ret', 'Nfix',
    'Meis1', 'Reln', 'Mdga1', 'Adgrf5', 'Npas1', 'Caln1', 'Ndst4', 'Sox14',
    'Frzb'
    ]
    return genes

def genes_in_imputed_merfish_data():
    imputed_genes = [
        'Ccdc3', 'Grp', 'Nos1', 'Otof', 'Dach1', 'Arhgef28', 'Marcksl1', 'Nkain3', 'Trp53i11', 'Npas3', 'Cntnap5a', 'Hrk', 'Pdgfc', 'Ryr3', 'Ccn3', 'Crym', 'Ccbe1', 'Prss12', 'Sgcd', 'Syt17', 'Pdzrn4', 'Timp2', 'Mapk3', 'Matn2', 'Smoc2', 'Zfpm2', 'Cep112', 'Pcsk5', 'Tox', 'Grin3a', 'Meis2', 'Mgat4c', 'Grm8', 'Prkd1', 'Ndst3', 'Crim1', 'Luzp2', 'Tmeff1', 'Rasl10a', 'Slc4a4', 'Cntn6', 'Zfhx4', 'Echdc2', 'Lratd1', 'Jsrp1', 'Alcam', 'Gsg1l', 'Pcdh17', 'Mkx', 'Gm43445', 'Mcc', 'Gucy1a1', 'Etv6', 'Bicc1', 'Calb1', 'Rspo2', 'Cdh4', 'Col25a1', '9530059O14Rik', 'Stum', 'Synpr', 'Grm1', 'Cux2', 'Rorb', 'Cpne6', 'Cdh7', 'Cdh13', 'Rps6ka2', 'Kcnip2', 'Rtn4rl1', 'Greb1l', 'Cpne9', 'Col19a1', 'Pparg', 'Pde7b', 'Gnal', 'Dusp18', 'C1ql3', 'Robo1', 'Zfp804b', 'Gm30382', 'Rasgrf2', 'Nav1', 'Man1a', 'Fxyd6', 'Necab1', 'Prkcg', 'Ttc28', 'Shisal1', 'Tmem196', 'Itga8', 'Pcdh11x', 'Gpr83', 'Gpr88', 'Medag', 'Pou3f2', 'Rgs8', 'Slc24a4', 'Bhlhe22', 'Gpc6', 'Ankrd6', 'Kitl', 'Rskr', 'March4', 'Tafa1', 'Slit3', 'Ptprf', 'Tnnc1', 'S100a6', 'Nectin3', 'Stard8', 'Stxbp6', 'Kcnk2', 'Kcnh5', 'Rcan2', 'Igsf3', 'Lamp5', 'Cpne8', 'Adcyap1', 'Neurod1', 'Wls', 'Adam2', 'Cdh20', 'Slc30a3', 'Tafa2', '4921539H07Rik', 'Cdh6', 'Tshz2', 'Phactr2', 'Tmtc2', 'Pdzrn3', 'Cpne4', 'Rmst', 'Zmat4', 'Scube1', 'Epha10', 'Spats2l', 'Hrh3', 'Chn2', 'A830036E02Rik', 'Ptchd4', 'Myo16', 'Gm20063', 'Coch', 'Sema6a', 'Ddit4l', 'Wnt10a', 'Whrn', 'Adam33', 'Gm12371', 'Rspo1', 'Ptgs2os', 'A930012L18Rik', '4930447N08Rik', 'Col26a1', 'Egfem1', 'Camk2d', 'B230216N24Rik', 'Adcy8', 'Krt12', 'Brinp3', 'Sntg2', 'Camk2n2', 'Cbln2', 'Prr16', 'Zfp462', 'Gm28905', 'Ntng1', 'Atp1b2', 'Osbpl3', 'Rgs20', 'Galntl6', 'Kctd1', 'Lhfp', 'Igfbp6', 'Pantr1', 'Nr4a1', 'Cdkn1a', 'Vstm2l', 'Adcy2', 'AI593442', 'Syndig1', 'Cdh8', 'Kcnc2', 'Cdh12', 'Sorcs1', 'Ephb1', 'Zbtb16', 'Akap5', 'Enpp2', 'Kcnab1', 'Epha6', 'Synj2', 'Sept9', 'Cntn5', 'Rgs7', 'Cacna1a', 'Rgs6', 'Baalc', 'Fam135b', 'Ramp1', 'Mpped1', 'St6galnac5', 'Nfix', 'Edil3', 'Kcnip3', 'Limch1', 'C530008M17Rik', 'Socs2', 'Spock3', 'Dgkg', 'Sema6d', 'Lcorl', 'Kcnf1', 'Bdnf', 'Maml3', 'Mgll', 'Arc', 'Grm3', 'Cnih3', 'Gm11549', 'Sema3a', 'Ccnd1', 'Htr2a', 'Tenm3', 'Pitpnc1', 'Sulf2', 'Pou3f1', 'Hs3st4', 'Cbln4', 'Banf2', 'Pcsk1', 'Adra1a', 'Trbc2', 'Cd302', 'Hunk', 'Afap1l1', 'Plcb4', 'Kcnh4', 'Gm2164', 'Pard3', 'Rph3a', 'Zeb2', 'Dkk3', 'Flrt2', 'Ovol2', 'Gm40841', 'Csgalnact1', 'Runx1t1', 'Etnk2', 'Slc35f4', 'Cnr1', 'Trps1', 'Runx2', 'Prag1', 'Arhgap31', 'Atp6ap1l', 'Kcng1', 'Nr2f2', 'Scn7a', 'Clec18a', 'Eif4ebp1', 'Dscaml1', 'Sema3e', 'Sox8', 'Adgrg6', 'Slc26a4', 'Prex1', 'Igsf21', 'Kctd4', 'Atp2b4', 'Epb41l2', 'Gm34567', 'Ldb2', 'Gabrg3', 'Pak6', 'Gm33228', 'C730002L08Rik', 'Nbl1', 'Galnt17', 'Stk32c', 'Nfib', 'Dgkb', 'Kcnj4', 'Gcnt2', 'Chst2', 'Fst', 'Mamdc2', 'Adra2c', 'Ptgs2', 'Cpne5', 'Chl1', 'Scn3b', 'Ntrk3', 'Nell1', 'Fosl2', 'Galnt14', 'Phf21b', 'Nptx2', 'Itga6', 'Dusp5', 'BC006965', 'Sertm1', 'Cacng4', 'Cdk18', 'Sox9', 'Chrna4', 'Adamtsl1', 'Sdk2', 'Zfp804a', 'Peak1', 'Nrp1', 'Mylk3', 'Gm2824', 'Cd34', 'Lin28b', 'Clmp', 'Trhde', 'Arhgap10', 'Gm15398', 'Exph5', 'Nrep', 'Chrm3', 'Trpc6', 'A330008L17Rik', 'Cemip', 'Ppfibp1', 'Lhx2', 'Hrh2', 'Cux1', 'Inhba', 'Tmtc1', 'Gm28175', 'Tshz1', 'Shisa6', 'Lrrc55', 'Slc17a6', 'Gm13629', 'Boc', 'Rnd3', 'Myo1b', 'Prdm8', 'Pou3f3', 'Rims3', 'Dleu2', 'Nectin1', 'Chrm2', 'Lemd1', 'Mmel1', 'Plcxd2', 'Sphkap', 'Gm3764', 'Xkr6', 'Cckbr', 'Sytl2', 'Cadps2', 'Olfm3', 'Serinc2', 'Igfbp4', 'Antxr1', 'Serpinb8', 'Inf2', 'Anxa11', 'Gm17167', 'Gm16599', 'Tmem132d', 'Sparcl1', 'Btbd3', 'Arhgap15', 'Sox5', 'Mlip', 'Pcdh20', 'Dok5', 'Ntng2', 'Hs3st2', 'Hrh1', 'AI504432', 'Lmo3', 'A330102I10Rik', 'Stac2', 'Fmn1', 'Shisa9', 'Crip2', 'Mmp17', 'Camk1g', 'Tmem108', 'Lynx1', 'Plxdc1', 'Snx25', 'Il17ra', 'Slc24a2', 'Sntb2', 'Ubash3b', 'Plcl1', 'Gm50304', 'Dkkl1', 'Klhdc8b', 'Gm4876', 'Fstl5', 'Doc2a', 'Gm15680', 'Thsd7a', 'Ankfn1', 'Lypd1', '4930467D21Rik', 'Cntnap5b', 'Pld5', 'Ccnd2', 'Rprm', 'S100a10', 'Rbms1', 'Gm20754', 'Kirrel3', 'Sel1l3', 'Spon1', 'Itga4', 'Grik1', 'Trpm3', 'Ptbp3', 'C030013G03Rik', 'Dcbld2', '1700047F07Rik', 'Crispld1', 'Sept4', 'Sgpp2', 'Tox3', 'Sdk1', 'Barx2', 'Samd5', 'Rasal1', 'Plppr1', 'Lamc2', 'Plppr3', 'Htr2c', 'Rgs10', 'Hgf', 'Mmd2', 'Ccn4', 'A2ml1', 'Ikzf2', 'Plxnd1', 'Htr1f', 'Vstm2b', 'Car4', 'Pcdh19', 'Trpc3', 'Pamr1', 'Ptprm', 'Fras1', 'S100b', 'Cxxc4', 'Endou', 'Gpc5', 'Tspan9', 'Slc6a7', 'Trib2', 'Tmem44', 'Ell2', 'Fat1', 'Phlda1', 'Zeb1', 'Colq', 'Nefm', 'Iqgap2', 'Prrg1', 'Gm3294', 'Wwtr1', 'Tmem232', 'L3mbtl4', 'Dpp4', 'Kcnab3', 'Gm26691', 'Masp1', 'Ano4', 'Diaph3', 'Sema3d', 'Cxcl12', 'Ptpru', 'Onecut2', 'Il1rapl2', 'Klf5', 'Palmd', 'Kcnc4', 'Amotl1', 'Mei4', 'Gm44644', 'Fos', '9630014M24Rik', 'Lypd6', 'Epb41', 'Esrrg', 'Mtcl1', 'Cav2', 'Gm9866', 'A830009L08Rik', 'Sh3rf1', 'Ephb6', 'Cryab', 'Galnt9', 'Itgav', 'Bcl11a', 'Grik3', 'Htr1b', 'Inhbb', 'Bhlhe40', 'Pvt1', 'Grm2', 'Slc24a3', 'Hs3st5', 'Cdh9', 'Rxfp1', 'Fam43a', 'Gm29514', 'Bok', 'Sstr2', 'Nr4a3', 'Nr4a2', 'Ftl1-ps1', 'Lhfpl3', 'Rnf144b', 'Eepd1', 'Lgi2', 'Scg2', 'Hs6st2', 'Mt1', 'Rarb', 'Gabra5', 'B3galt2', 'Pou6f2', 'Man2a1', 'Susd1', 'Sox11', 'Cntnap4', 'Lypd6b', 'Rell1', 'Kcna6', 'Cdh18', 'Bmp3', 'Bmpr1b', 'Ptpre', 'Sulf1', 'Gnb4', 'Grik4', 'Nnat', 'Chst11', 'Arhgap25', 'Sema5b', '8030453O22Rik', 'Osr1', 'Plekha2', 'Cntnap3', 'Adgrd1', 'Samd4', 'Bmp2', 'Sowahb', 'Thsd4', 'Plch2', 'Adamts18', 'Rftn1', 'Efnb3', 'Ramp3', '4933406J09Rik', 'Bcl11b', 'Fgf10', 'Cwh43', 'Drd1', 'Megf11', 'Slc6a11', 'Oprk1', 'Trpc4', 'Gm2694', 'Wnt4', 'Plcxd3', 'Cpne7', 'Angpt1', 'Dnah14', 'Syt10', 'Gm10754', 'Pced1b', 'St6gal1', 'Cys1', 'Adamts17', 'Tet1', 'Slc9b2', 'Slc26a8', 'Ptprk', 'Vgf', 'Lrrn2', 'Gm4258', 'Pitpnm3', 'Nefl', 'Etv5', 'Cxxc5', 'Vav3', 'Gm49678', 'Grb10', 'Cd83', 'Rgs12', 'Cbln1', 'Herc6', 'Fxyd1', 'Gpd1', 'Me3', 'St3gal1', 'Trpc5', '4930447C04Rik', 'Shroom2', 'Sash1', 'Gm16083', 'Thap3', 'A230006K03Rik', 'Coro1c', 'Cotl1', 'Prmt2', 'Rhou', 'Man1c1', 'Adamts3', 'Phlda3', 'Gfra2', 'Syt12', 'Col6a1', 'Fhod3', 'Adgrl2', 'Itgb8', 'Epha4', 'Cdh11', 'Necab3', 'C130074G19Rik', 'Tesc', 'Crtac1', 'Kcnn3', 'Clmn', 'Hpcal1', 'Dpyd', 'Rab3b', 'Gpx3', 'Tmem117', 'Nek10', 'Chst9', 'Cd24a', 'Gng4', 'C2cd4c', 'Vegfd', 'Wscd1', 'D030068K23Rik', 'Dkk2', 'Kcnmb2', 'Nnmt', 'Scn9a', 'Tmem91', 'Arsj', 'Dpysl5', 'Ntsr1', 'Vat1', 'Gm32647', 'Tmcc3', 'Rnf144a', 'Paqr7', 'Pik3ip1', 'Prss22', 'Oprl1', 'Cyp7b1', 'Prex2', 'Adra1b', 'Fjx1', 'Tspan17', 'Sccpdh', 'Ldlrad3', 'Ppp1r14c', 'Sh3d19', 'Grem2', 'Wscd2', '6530403H02Rik', 'Nrp2', 'Wnt7b', 'Dpysl3', '1500009L16Rik', 'Tmem200a', 'Ror1', 'Znrf3', 'Zfp423', 'Ddr1', 'Paqr8', 'Slc44a5', 'Gng12', 'Srgap1', 'D430019H16Rik', 'Akap13', 'Inpp4b', 'Blnk', 'Sv2c', 'Npy', 'Gm1604a', 'Gm6209', 'Ptprz1', 'Gm19744', 'Asic4', 'Gm10605', 'Alkal1', 'Npy2r', 'Lpl', 'Smim3', 'Thsd7b', 'Maml2', 'Unc13c', '5330416C01Rik', 'Nckap5', 'Rai14', 'Rhbdl3', 'Vwc2l', 'Nr3c2', 'Rps6ka5', 'Map2k6', 'Foxo1', 'Pxdn', 'Jph1', 'Ier5', 'Sgk1', 'Dpf3', 'Prtg', 'A830031A19Rik', 'Col5a2', 'Ston2', 'Dner', 'Tll2', 'Tmcc2', 'Sema3c', 'Tmem150c', 'Apaf1', 'Rassf3', 'Klhdc8a', 'Sorcs2', 'Pkib', 'Lrtm2', 'B130024G19Rik', 'Raver2', 'Met', 'Ust', 'Hsd11b1', 'Glra3', 'Rreb1', 'Nrsn2', 'Tmem163', 'Abat', 'Prkg2', 'Plb1', 'Antxr2', 'Tanc1', 'Hbegf', 'Pip5k1b', 'Aldh1l1', 'Adam19', 'Slc39a6', 'Tcap', 'Ptpro', 'Lrrtm1', 'Galnt18', '2600014E21Rik', 'Ppargc1a', 'Dgat2', 'Deptor', 'Dtl', 'Igfbp5', 'Net1', 'Cyp26b1', 'Glra2', 'Mtus1', 'Tmie', 'Samd14', 'Zfp831', 'Wfdc18', 'Egln3', 'Lamb1', 'Cd44', 'Gpc4', 'Pstpip1', 'Gm5149', 'Dcdc2a', 'Gm29674', 'Hs3st1', 'Rgs4', 'Tle1', 'Abracl', 'Slc8a3', 'Lama4', 'Spint2', 'Fbn2', 'Zdhhc22', 'Plekha7', 'Zar1l', 'Etv1', 'Fezf2', 'Serpine2', 'Npnt', 'Parm1', 'Atp8b1', 'B3glct', 'Ptgfrn', 'Bmper', 'Shc4', 'Tmem215', 'Cacna1i', 'Pcp4', 'Wipf3', 'Rab38', 'Gm13974', 'Gm10649', 'Esr1', 'Zfp608', 'Steap2', 'Gm16263', 'Ar', 'Synm', 'Aldh2', 'Gm48530', 'Per3', 'Ablim3', '1110032F04Rik', 'Islr2', 'Ccnb1', 'Inka2', 'Rasd2', 'Sema5a', 'Ighm', 'Nfia', 'Car12', 'Myl4', 'Cpa6', 'Fhad1', 'Robo3', 'Ddo', 'Adssl1', 'Dusp6', 'Ddah1', 'Gadd45a', 'Penk', 'H2-T23', 'Gm48623', 'Lipg', 'Incenp', 'Fbln2', 'Rgma', 'Gpr68', 'Mettl24', 'Ankrd44', 'Gm28578', 'Sept6', 'Nxph3', 'Slc5a5', 'Atp10a', 'Disp3', 'Neto2', 'Rflnb', 'Lpp', 'Opn3', 'Gm35161', 'St8sia2', 'Susd5', 'Lgr5', 'Tnfaip8l3', 'Tspan2', 'Ppfia4', 'Ccdc136', 'Abcd2', 'Cyp11a1', 'Tcerg1l', 'Ndrg2', 'Rgs16', 'Fam20a', 'Coro6', 'Scnn1a', 'Chst8', 'Gcnt4', 'Rnd2', 'Zdhhc23', 'Ildr2', 'Dleu7', 'Pde1c', 'Utrn', 'Jam2', 'Prlr', 'Fam3c', 'Fgfr1', 'Ifit2', 'Adamts2', 'Pygo1', 'E230016M11Rik', 'Klhl13', 'Ptger3', 'Rnf152', 'Bcl2', 'Col12a1', 'Gm10635', 'Cdh24', 'Lats2', 'Col15a1', 'Ank1', 'Fbxo32', 'Neu2', 'Dock10', 'Kat2b', 'Batf3', 'Olah', 'Itgb3', 'Cplx3', 'Fat4', 'Tox2', 'Gm10125', 'Spsb1', 'Vrk2', 'Ptk7', 'Ctsz', 'Arl4c', 'Jam3', 'Nhsl2', 'Gm27153', 'Traf5', 'Gm20646', '2010204K13Rik', 'Ppp1r1b', 'Mxra7', 'Acvr1c', 'Sema7a', 'Scn4b', 'Vamp1', 'Them6', 'Myh14', 'Gm40331', 'Cygb', 'Resp18', 'Pttg1', 'Dbi', 'Maf', 'Hspb3', 'Dapk2', 'Cthrc1', 'Cntnap1', 'Kcna1', 'Doc2b', 'Sez6', 'BC030500', 'Vav2', 'Zfp703', 'Gm34544', 'Egr4', 'Lsm11', 'Thrsp', 'Gfra1', '5033430I15Rik', 'Fgf11', 'Mylk', 'Gm13205', 'Rxrg', 'Efcab1', 'Scml4', 'Sema4g', 'Dysf', 'Wfs1', 'Eda', 'Fhl1', 'Pts', 'Gm36251', 'Lst1', 'Zfp618', 'Amz1', 'Pde9a', 'Fam102b', 'Col24a1', 'Lgals1', 'Fign', 'Gask1b', 'Sipa1l2', 'Parva', 'Gm20752', 'Nhs', 'Kctd12', 'Col11a1', 'Fap', '2700069I18Rik', 'Frzb', 'Pfkfb3', 'Adgra3', 'Gm14636', 'Nrip3', 'Ctxn2', 'Nipal3', 'Rab31', 'Dact2', 'Bcl6', 'Plpp4', 'Lpar1', 'Tle3', 'Pdlim1', 'Fndc5', 'Gprin3', 'Ehbp1l1', 'Epha3', 'Crhr1', 'Sall2', 'Gm49932', 'Mgat5b', 'Hkdc1', 'Glt8d2', 'Slc16a10', 'Pde8b', 'Pdia5', 'Foxo6', 'Ap1s2', 'Kazald1', 'Htra1', 'Ifi27', 'Mgst3', 'Plekho1', 'Kcnt1', 'Gria3', 'Tubb2a', 'Neto1', 'Nsun7', 'Evc2', 'Ctsc', 'Itpkb', 'Tunar', 'Gpr155', 'Kazn', 'Mei1', 'Dcbld1', 'Lrrc57', 'Ccng1', 'Galnt16', 'Prss23', 'Ccdc80', 'Arhgap42', 'Fbn1', 'Igfbp7', 'Ackr3', 'Smim1', 'Rassf5', 'Metrnl', 'Gpc1', 'Gxylt2', '1700016K19Rik', 'Satb1', 'Hes1', 'Efcab6', 'Rspo3', 'Cflar', 'Rin2', 'St5', 'Kcnt2', 'Adam18', 'Mobp', 'Mas1', 'Fosb', 'Pim1', 'Gadd45g', 'Tnfaip6', 'Neb', 'Gadd45b', 'Csrnp1', 'Lbh', 'Nfil3', 'Gm32036', 'Gpr3', 'Shroom3', 'Tent5a', 'Nabp1', 'Mir670hg', 'Rgs9', 'Ism1', 'Smad7', 'Grk5', 'Npas4', 'Mapk4', 'Col23a1', 'Foxp2', 'Rnf182', 'Cachd1', 'Hhip', 'Scn5a', 'Vamp8', 'Ighg2c', 'Itga9', 'A230077H06Rik', 'Sh3bp4', 'Trpc7', 'Dcn', 'Cpne2', 'Oprd1', 'Wdr6', 'Npsr1', 'Gm13561', 'C130073E24Rik', 'Spag16', 'Drd2', 'Klhl1', 'Pdlim5', 'Abca8a', 'Tpbgl', 'Tmprss7', 'Cped1', 'Tacr1', 'Apcdd1', 'Ndrg1', 'Ppil6', 'Plce1', 'Csrp2', 'Vwa3a', 'Tgfbr3', 'Fam13a', 'Slc7a11', 'Dlk1', 'Pcdh8', 'Tmem255a', 'Arhgap6', 'Mgp', 'Airn', 'Myh7', 'March3', 'Gpr176', 'Piezo2', 'Mest', 'Mapk6', '1700016P03Rik', 'Elmo1', 'Tgfb2', 'Spry2', 'Unc5b', 'Baz1a', 'Tacstd2', 'Myocd', 'Txk', 'Sfrp2', 'Baiap3', 'Chsy3', 'Galnt7', 'Adamts1', 'Cgref1', 'Tiparp', 'Sap30', 'Zdbf2', 'Rnf128', 'Coro1a', 'Prss35', 'Igfn1', '4833415N18Rik', 'Llgl2', 'Dmkn', 'Cavin3', 'S100a3', 'Dock6', 'Col27a1', 'Kiz', '9330158H04Rik', 'Arhgef15', 'Peli2', 'Usp29', '1700023F02Rik', '4930407I19Rik', 'Crispld2', 'Glis1', 'Cfap44', 'Tpd52l1', 'Kcnk13', 'Gab2', 'Hap1', 'Ephb2', 'Fhl2', 'Stat5b', 'Tiam1', 'Nt5dc3', 'Chrdl1', 'G630016G05Rik', 'Vgll4', 'Kcnip1', 'Adra2a', 'Kif26b', 'Cgnl1', 'Lcp1', 'Cntnap5c', 'Gm6999', 'Fibcd1', 'Ccdc85a', 'Frmd3', 'Rerg', 'Olfm4', 'Gm41414', 'Dio3', 'Fam163b', 'Twist2', 'Tpbg', 'Lxn', 'Dipk2a', 'Yap1', 'Sik1', 'Egr2', 'Agtr1b', 'Tll1', 'Oxtr', 'Arhgap18', 'Ghr', 'Ankrd63', 'Dchs2', 'Zfp503', 'Reln', 'Npy1r', 'Igfbp3', 'Zfp811', 'Eya1', 'Glb1', 'Krt9', 'Gm26542', 'Fndc1', 'Scube2', 'Vat1l', 'Grasp', 'Ier3', 'Gdpd5', 'Mdga1', 'Erbin', 'Lrrtm2', 'Gm15270', 'Pcp4l1', 'Lpin1', 'Gm13052', 'Htr1a', 'Cabp7', 'Cdhr1', 'Elk3', 'Adarb2', 'Gm26782', 'Kremen1', 'Bcat1', 'Lsp1', 'F730043M19Rik', 'Jup', '1700019D03Rik', 'Cntn2', 'Gm40518', 'Nxph1', 'Ltbp1', 'B3gat2', 'Pard3b', 'Sfmbt2', 'Adam12', 'Ccdc141', 'Lepr', 'Gm45323', 'Insyn2b', 'Rab26', 'Adcy9', 'Cfap54', 'Pwwp2b', 'Gm47405', 'Spns2', 'Dcx', 'Kit', 'Sh3gl3', 'Car2', 'Serpinb9', 'Mt2', 'Tpm4', 'D830030K20Rik', 'Cacng5', 'Mctp2', 'Flrt1', 'Chd7', 'Cblb', 'Pde3a', 'BB557941', 'Cald1', 'Car3', 'Arhgap24', 'Itga7', 'Eps8', 'Cd63', 'D430036J16Rik', 'Alk', 'Sostdc1', 'Col4a1', 'Tnfrsf19', 'Vcan', 'Sncaip', 'Prkcd', '9530036O11Rik', 'Slc9a5', 'Golim4', 'Gm15721', 'Plekhh2', 'Ccn2', 'Gm50100', 'Dusp2', 'Homer2', 'Layn', 'Ppfibp2', 'Anxa5', 'Lix1', 'Tgfbr1', 'Rbm24', 'Serinc5', 'Ano3', 'Cbfb', 'Gm12064', 'Slc1a2', 'Gm11418', 'Acvr2a', 'Sh3pxd2b', 'Col18a1', 'Rgcc', 'Alkal2', 'Ascl1', 'Lrig1', 'Trib1', 'Gm4128', 'Midn', 'Sik2', 'Kdm6b', 'Armc2', 'Colgalt2', 'Osbpl10', 'Gm13601', 'Kif17', 'Cops5', 'Hcn2', 'Mecr', 'Cog4', 'Ccdc88c', 'Iqce', 'Lncppara', 'Ubxn11', 'Utp3', 'Mtm1', 'Myo1d', 'Morc2a', 'Gm11417', 'Sema4a', 'Zfp385b', '2310002F09Rik', 'Caln1', 'Stard10', 'Asxl3', 'Ppp1r16a', 'Strip2', 'C030017B01Rik', 'Nptx1', 'Cartpt', 'Lmo1', 'Aldh1a1', 'Nmb', 'Tspan11', 'Cpm', 'Cracr2a', 'Pde11a', 'Ninj1', 'Tmem159', 'Npr3', 'Mtss1', 'Lifr', 'Hey1', 'Plpp3', 'Htr4', 'Ccnjl', 'Cdkn1c', 'Csf1', 'Gm30648', 'Dnah5', 'Wdr66', 'Parp8', 'Krt1', 'Slc16a1', 'Gm11290', 'Dusp1', '4930555F03Rik', 'Zcchc12', 'Stac', 'Lancl3', 'Gm45341', 'Oprm1', 'Gm2516', 'Rcan3', 'Btbd11', 'Tacr3', 'Arhgap12', 'Arhgef26', 'Itprid1', '4930590L20Rik', 'Mtmr10', 'Zfp536', 'Egr1', 'Ankrd33b', 'Fam53b', 'Ankrd35', 'Mgat5', 'Cdc42ep3', 'Stn1', 'Trhr', 'Adcy7', 'D16Ertd472e', '4833422C13Rik', 'Zbtb7c', 'Ranbp17', 'Gm12027', 'Glis3', 'Dbpht2', 'Fgf1', '1110002E22Rik', 'Nppc', 'Rgs2', 'Mn1', 'Tspan6', 'Pbx3', '9630002D21Rik', 'St8sia4', 'Bcl2l11', 'Syn3', 'Rasl11a', 'Lncbate10', 'Sh3bgrl2', 'Calb2', 'Necab2', 'Vwc2', 'Adgrg1', 'Rab27a', '4930539E08Rik', 'Id4', 'Ebf1', 'Gm12031', 'Prokr2', 'Sox6', 'Gm49906', 'Tekt5', 'Dsg2', 'Tns1', 'Trmt9b', 'Sfrp1', 'Trabd2b', 'Lama3', 'Sinhcaf', 'S1pr3', 'Cox6a2', 'B4galt1', 'Stard5', 'Lhfpl2', 'Pacsin2', 'Pxdc1', 'Col8a1', 'Rasl11b', 'Usp6nl', 'Il12a', 'D5Ertd615e', 'Fzd10os', 'Gm5820', 'Chrd', 'Plxdc2', 'Gm30371', 'Tmem164', 'Gng5', 'E130114P18Rik', 'Rcn1', 'Plagl1', 'Hcrtr2', 'Gm765', 'Jun', 'Slc22a4', 'Ntn4', 'Grb14', 'Chst15', 'Gm32442', 'Rasa3', 'Tenm1', 'AY036118', 'Gm17501', 'Myo1e', 'Amn', 'Trpv6', 'Kcnj16', 'Aldoc', 'Gm43154', 'Tm6sf1', 'Hcn3', 'Kctd8', 'Matn4', 'Patj', 'Gm47710', 'Relt', 'Gm48003', 'Rbp4', 'Erbb4', 'Gm20033', 'Maob', 'Klf3', 'Ccdc148', 'Htr7', 'Nacc2', 'Rbm20', 'Pygm', 'Rassf2', 'Map3k20', 'Lgi3', 'Tmem125', 'Gabrd', 'Mb21d2', 'Gm12930', 'Celf6', 'Tbc1d16', 'C130026L21Rik', 'Shf', 'B930095G15Rik', 'Hcn4', 'Cyp39a1', 'Rasl10b', 'Dclk3', 'St3gal6', 'Shisa3', 'Slc23a3', 'Rgs3', 'Tmem132e', 'Plxna1', 'Rxfp2', 'Adamts5', 'Slc36a1', 'Pcdh15', 'Rasgrp1', 'Lrrtm3', 'Satb2', 'Dlc1', 'Cacna2d3', '9130024F11Rik', 'Tshz3', 'Hivep1', 'Fxyd7', 'Map3k5', 'Rtl4', 'Pcdh10', 'Thrb', 'Dpy19l1', 'Kcnq5', 'Gabrb1', 'Nrsn1', 'Sgcz', 'Ptprt', 'Pde1a', 'Tenm2', 'Pcsk2', 'Spock1', 'Cntn4', 'Hlf', 'Etl4', 'Slc2a13', 'Neurod6', 'Cobl', 'Tyro3', 'Ptn', 'Cntn3', 'Igsf9b', 'Adora1', 'Kcnh1', 'Diras2', 'Cdyl2', 'Sorcs3', 'Ncam2', 'Kcnb2', 'Grin2a', 'Asic2', 'Khdrbs3', 'Hs6st3', 'Egr3', 'Pik3r1', 'Id2', 'Efna5', 'Ipcef1', '2900026A02Rik', 'Asap2', 'Slc35f1', 'Pde4a', 'Fat3', 'Dnajc21', 'Arap2', 'Olfm2', 'Cit', 'Ctnna3', 'Rnf112', 'Fstl4', 'Pcdh7', 'Garnl3', 'Vxn', 'Cck', 'Kctd16', 'Mpped2', 'Khdrbs2', 'Mbp', 'Nebl', 'Epha7', 'Cacng3', 'Pam', 'Jcad', 'Smarcd3', 'Hapln4', 'Tmem178', 'Ablim1', 'March1', 'Lrrk2', 'Grid2', 'Slc9a9', 'Cacna1g', 'Smad3', 'Bach2', '2610316D01Rik', 'Ajap1', 'Grip1', 'Mras', 'Nr2f1', 'Pls3', 'A830082K12Rik', 'Myrip', 'Naaladl2', 'Gm26871', 'Rimbp2', 'Adcyap1r1', 'Bbs9', 'St6gal2', 'Tmem145', 'Adgra1', 'Gm15478', 'Slit2', 'Fmnl1', 'Fam124a', 'Ptprr', 'Tbr1', 'Adk', 'Il1rap', 'Gabra4', 'Ak4', 'Rora', 'Zfp941', 'Ptpn3', 'Gabra3', 'Elavl2', 'Ldlr', 'Lrrc3b', 'Cbfa2t3', 'Ptchd1', 'Carmil1', 'Wnt9a', 'Nfkb1', 'Sh3kbp1', 'Ripor2', 'Sidt1', 'Pla2g4e', 'Dnm3', 'Orai2', 'Gpr153', 'Ptpn5', '2510009E07Rik', 'E130308A19Rik', 'Slc35f3', 'Chga', 'Epop', 'Prkca', 'Adcy5', 'Lrch1', 'Cdh22', 'Camk1', 'Nwd2', 'Lrrn3', 'Plaat1', 'Klhl32', 'Fbxo2', 'B2m', 'Chml', 'Cst6', 'Efhd2', 'Mir99ahg', 'Fbxo10', 'Cacnb2', 'Klf10', 'Stim2', 'Lrp1b', 'Ctxn1', 'Gm48957', 'Hmgcr', 'Sec24d', 'Mpp6', 'Epb41l4b', 'St6galnac3', 'Bace2', 'Lmo4', 'Ptk2b', 'Cabp1', 'Rbfox1', 'Pde4d', 'Scg3', 'Car10', 'Ntm', 'Ncald', 'Asap1', 'Prkcb', 'Itpr1', 'Grm7', 'Cib2', 'Mitf', 'Tbc1d1', 'Psd2', 'Zmiz1os1', 'Dpp10', 'Unc5d', 'Lrrtm4', 'Cacng2', 'Mctp1', 'Lingo2', 'Pmepa1', 'Kcnh7', 'Cdh10', 'Robo2', 'Frmd6', 'Slc17a7', 'Ephx4', 'Itpka', 'Rtn4r', 'Hpca', 'Tagln3', 'Ttyh1', 'Camk2g', 'Nsg1', 'Ngef', 'Rasgrf1', 'Ociad2', 'Plk2', 'Npas2', 'Fnbp1l', 'Rasgef1b', 'Tiam2', 'Pid1', 'Sesn3', 'Kcnk9', 'Dusp26', 'Farp1', 'Dgkh', 'Wasf3', 'Kcnv1', 'Frmd5', 'Shisa4', 'Tmem158', 'Dab2ip', 'Cdon', 'Lyzl4', 'Gm10115', 'Sox4', 'Aff2', 'Mef2c', 'D430041D05Rik', 'Clstn2', '5730522E02Rik', 'Gm32509', 'Fkbp1b', 'Nxpe4', 'Uap1', 'Vstm2a', 'Tmod1', 'Rnf180', 'Lmo7', 'Nrg2', 'Hsd17b7', 'Cspg5', 'Kcnc1', 'Kcnh3', 'Spred2', 'Cplx1', 'Hdac9', 'Cap2', 'Sorl1', 'Arnt2', 'Pde4b', 'Osbpl1a', 'Adcy1', 'Cadm3', 'Gng2', 'Ppp1r1a', 'Tmsb10', 'Gabra1', 'Dgki', 'Fam189a1', 'Nrn1', 'Gpr22', 'Pex5l', 'Ptprg', 'Ak5', 'Xkr4', 'Prkg1', 'Dcc', 'Mast4', 'Cplx2', 'Tmem132b', 'Diaph2', 'Cited2', 'Slc7a14', 'Cds1', 'Slitrk1', 'Igf1r', 'Zdhhc2', 'Mt3', 'Dusp3', 'Rapgef5', 'Magi1', 'Nlgn1', 'Nol4', 'Hpcal4', 'Nrg1', 'Tacc1', 'Hecw1', 'Ppm1l', 'Lin7a', 'Pdp1', 'Adrb1', 'Pde1b', 'Efnb2', 'Sv2b', 'Brinp2', 'Wwc1', 'Add3', 'Marc2', 'Ackr1', 'Unc5c', 'Gap43', 'Elavl4', 'Ppp2r2b', 'Stmn2', 'Agbl4', 'Stx1a', 'Plxna4', 'Prmt8', 'Rprml', 'Nrgn', 'Fam81a', 'Gda', 'Srgap3', 'Gabbr2', 'Ldlrad4', 'Baiap2', 'Kcnd3', 'Prr13', 'Tmem47', 'Gabra2', 'Gria4', 'Tenm4', 'Creg2', 'Camk4', 'Neurod2', 'Pdgfb', 'Hcn1', 'Kcna2', 'Mal2', 'Xylt1', 'Nuak1', 'Snx7', 'Scn1a', 'Kcnj3', 'Mir100hg', 'Gpr26', 'Tafa5', 'Cd200', 'Phf24', 'Tmem178b', 'Stmn1', 'Gng3', 'Arl15', 'Nell2', 'Ralyl', 'B3gat1', 'Mir124-2hg', 'Nyap2', 'Lingo1', 'Tnr', 'Arpp21', 'Klf9', 'Cacna2d1', 'Dscam', 'Syt7', 'Cacna1e', 'Csmd2', 'Nos1ap', 'Gng13', 'Rgs17', 'Dip2c', 'Zbtb18', 'Tmeff2', 'Camkk2', 'Tspan13', 'Enc1', 'Nr3c1', 'Brinp1', 'Ptprd', 'Mical2', 'Cnksr2', 'Lzts1', '2010300C02Rik', 'Rap1gap2', 'Marcks', 'Zmiz1', 'Junb', 'Zdhhc14', 'Cdkl5', '6330403K07Rik', 'Dab1', 'Lrfn2', 'Msra', 'Mast3', 'Chst1', 'Slc8a2', 'Lrrc4c', 'Prickle1', 'Snca', 'Slc6a17', 'Dlgap2', 'Gpm6b', 'Gas7', 'Kcnq3', 'Pak7', 'Ddn', 'Camkv', 'Chrm1', 'Syt16', 'Sorbs2', 'A830018L16Rik', 'Sez6l', 'Pdzd2', 'Kcnmb4', 'Cdk14', 'Kcnj6', 'Aff3', 'Tcf4', 'Syne1', '1110008P14Rik', 'Homer1', 'Plcb1', 'Pde2a', 'Syt13', 'Vsnl1', 'Serpini1', 'Fam155a', 'Nav2', 'Efr3a', 'Olfm1', 'Slc8a1', 'Gnas', 'Dapk1', 'Ppm1e', 'Pea15a', 'Oxr1', 'Shank1', 'Dmd', 'Nrcam', 'Ly6e', 'Gpr158', 'Miat', 'Golga7b', 'Nudt4', 'Scn1b', 'Arhgdig', 'Nptxr', 'Pknox2', 'Ube2ql1', 'Pnmal2', 'Arhgap20', 'Frmpd4', 'Gnai1', 'Synpo', 'Kcnip4', 'Camk2n1', 'Kcnb1', 'Il1rapl1', 'Syn2', 'Fut9', 'Rbfox3', 'Rgs7bp', 'Unc13b', 'Rps6ka3', 'Pgbd5', 'Zfp365', 'Grin2b', 'Camk2a', 'Kalrn', 'Ntrk2', 'Grm5', 'Adgrl3', 'Csmd1', 'Rasgef1a', 'Basp1', 'C130071C03Rik', 'Nrxn3', 'Cadps', 'Pde10a', 'Ryr2', 'Cadm1', 'Foxg1', 'Sirpa', 'Camk1d', 'Atp2b2', 'Atp2b1', 'Phactr1', 'Elmod1', 'Ly6h', 'Uqcc2', 'Fabp3', 'Stxbp5l', 'Tspan5', 'Gria1', 'Rapgef4', 'Atp8a1', 'Dlg1', 'Sipa1l1', 'Ppp1r16b', 'Thy1', 'Cadm2', 'Epha5', 'Nav3', 'Prickle2', 'Nedd4l', 'Samd12', 'Psd3', 'Lrfn5', 'Dgkz', 'Gabrb2', 'Nkain2', 'Lsamp', 'Grid1', 'Sh3rf3', 'Jph4', 'Dock4', 'Numb', 'Kcnd2', 'Tpm1', 'Slc7a8', 'Lgi1', 'Lrrc8b', 'Wdr17', 'Jdp2', 'Nrg3os', 'Oip5os1', 'Pcdh9', 'Gm20642', 'Poc1a', 'Ypel1', 'Cx3cl1', 'Schip1', 'Dok6', 'Pitpnm2', 'Lrrc7', 'Cacnb4', 'Celf2', 'Opcml', 'Chn1', 'Auts2', 'Nlk', 'Cttnbp2', 'Enox1', 'Tmem132a', 'Atp1a1', 'Garem1', 'Fbxw7', 'B3galt1', 'Syt1', 'Dusp14', 'Prkce', '3110039M20Rik', 'Plxna2', 'Ppm1h', 'Ttc9b', 'Fam49a', 'Reps2', 'Ccl27a', 'Dlgap1', 'Ldha', 'Unc5a', 'Sept8', 'Ext1', 'Syt4', 'Pbx1', 'Fam131a', 'Osbp2', 'Rab3c', 'Cntn1', 'B230209E15Rik', 'Atrnl1', 'Kcnma1', 'Trim9', 'Kcnj9', 'Csmd3', 'Tnik', 'Nsg2', 'Grik2', 'Rims1', 'Nrg3', 'Kif5c', 'Apba2', 'Pgm2l1', 'Sntg1', 'Arhgap26', 'Mdga2', 'Clstn1', 'Uchl1', 'Mapk10', 'Shank2', 'Slc12a5', 'Erc2', 'Sncb', 'Hivep2', 'Frrs1l', 'Napb', 'Dnajc6', 'Celf4', 'Rtn1', 'Amph', 'Anks1b', 'Plppr4', 'Tuba4a', 'Fgf14', 'Large1', 'Sh3gl2', 'Rian', 'Pacsin1', 'Prkar1b', 'Scn2a', 'Gria2', 'Atp6v1g2', 'Syp', 'Ppp2r2c', 'Myt1l', 'Lrp8', 'Kif1b', 'Snhg11', 'Phyhip', 'Otud7a', 'Dnajb5', 'Slc4a10', 'Camkk1', 'Iqsec1', 'Hecw2', 'Ccser1', 'Aldoa', 'Susd4', '6430548M08Rik', 'Gabrb3', 'Srcin1', 'Faim2', 'Spock2', 'Tppp', 'Pak1', 'Adgrb3', 'Negr1', 'Dlg2', 'Ctnna2', 'Fgf12', 'Dclk1', 'Ank2', 'Syt11', 'Map1b', 'Magi2', 'Ncam1', 'Ensa', 'Nrxn1', 'Cntnap2', 'Bsn', 'Macrod2', 'Gnao1', 'Nbea', 'Ppp1r9a', 'Ank3', 'Slc39a10', 'Syn1', 'Stmn3', 'Snrpn', 'Pcsk1n', 'Snap25', 'Atp1b1', 'Bex2', 'Ndrg4', 'Scg5', 'Ctnnd2', 'App', 'Dock3', 'Rims2', 'Meg3', 'Arfgef3', 'Sv2a', 'Rtn3', 'Slc25a22', 'Ywhah', 'Cdk5r1', 'Sult4a1', 'Eef1a2', 'Gabrg2', 'Slc2a3', 'Ina', 'Dync1i1', 'Mmp16', 'Cyfip2', 'Dnm1', 'Calm2', 'Ppfia2', 'Ndst4', 'Qrfpr', 'Hspa2', 'Ptpn14', 'Filip1', 'Igsf11', 'St18', 'Ebf2', 'Gng7', 'Tfap2d', 'Sox2ot', 'Zbtb20', 'Gtf2ird1', 'Fam126a', 'Fcor', 'Bves', 'Zic1', 'Adamts9', '9530026P05Rik', 'Ndnf', 'Slitrk2', 'Fads2', 'Grm4', 'Abi3bp', 'Myo5b', 'Syndig1l', 'Trim54', 'Mafb', 'Tmem268', 'A530058N18Rik', 'Stc1', 'Gm34466', 'Lrrn1', 'Fstl1', 'Crh', 'Ly6g6e', 'Gabrg1', 'Klhl14', 'Emid1', 'Syt9', 'Acp6', 'Gm47033', 'Dpy19l3', 'Lama2', 'Cidea', 'Dhrs3', 'Tes', 'Gulp1', 'Cacna2d2', 'Ntn1', '5830408C22Rik', 'Cxcl14', 'Cacna1h', 'Stpg1', 'Fyb2', 'Tmem35a', 'Tshr', 'Klf12', 'Slc6a1', 'C1ql1', 'Gng8', 'Pdyn', 'Rilpl1', 'Cdkl4', 'Rassf8', 'Chrna7', 'Vgll3', 'Igfbpl1', 'Zic5', 'Frmpd3', 'Gm13481', 'Ecel1', 'Popdc3', 'Vit', 'Tns3', 'Nts', 'D630023F18Rik', 'Celsr1', 'Slc1a3', 'Gpr101', 'Plk5', 'Slc29a4', 'Krt2', 'Kcng2', 'Frmd4b', 'Gm15283', 'Ccdc162', 'Smoc1', 'Dnah9', 'Sla', 'Gm13986', 'Mybpc1', 'Stard13', 'Fam184b', 'Slit1', 'Cc2d2b', 'Minar1', 'Nexn', 'Tmem65', 'Ddit4', 'Pdk1', 'Tmtc4', 'Fbxl7', 'Igfbp2', 'Ngb', 'Gm28050', '4930509J09Rik', 'Ntn5', 'Btg3', 'Hectd2', 'Adcy10', 'Gm31135', 'Gm42864', 'Spata13', 'Rfx3', 'Retn', 'Vegfc', 'Dsc3', 'Hmcn1', 'Fgf9', 'Lef1', 'Rasgrp2', 'Aldh1a3', 'Galnt3', 'Nefh', 'Arhgef6', 'Ntf3', 'Fermt1', 'Plch1', '4933424G05Rik', 'Naa11', 'Adgrg2', 'Plekhg1', 'Cldn1', 'Mme', 'Tmem255b', 'Wnt5a', '9330185C12Rik', 'Nrtn', 'Gm9989', 'Gpr12', 'Gbe1', 'Ngf', 'Itgbl1', 'Ccne1', 'Tgfa', 'Igf1', 'Adamts6', 'Slc38a3', 'Fam169b', 'Cebpd', 'Gm49164', '3110099E03Rik', 'Gm31698', 'Gm28376', 'Gprin1', 'Bend5', 'Ascc1', 'Magi3', 'Kcnn2', 'Sertad1', 'Parvb', 'Arhgef10l', 'Fam214a', 'Abca8b', '4921511C10Rik', 'Skil', 'Gprc5b', 'Prcd', 'Rab27b', 'Grip2', 'Cmpk2', 'Ttc9', 'Syt6', 'Tac1', 'Pappa', 'Igf2bp2', '4930426D05Rik', 'Ednrb', 'Rhoq', 'Hipk2', 'Slitrk4', 'Zfhx3', 'Ifitm10', 'Kcns2', 'St8sia1', 'Syt2', 'Mpp3', 'Rasgef1c', 'Manba', 'Armh4', 'Prr36', 'Fam13c', 'Ush2a', 'Wnt2', 'Crb1', 'Kcna4', 'Gm12649', 'Akain1', 'Flrt3', 'Pnmt', 'Neurl1b', 'Nab1', 'Chst7', 'Tgfbr2', 'Rapgef3', 'Notch2', 'Kirrel', 'Mrap2', 'Ppm1m', 'Lurap1l', 'Gsdme', 'Crybg3', 'Gm19303', 'Fibin', 'Kndc1', 'Olfml2b', 'Mirt1', 'Timp3', 'Dnah11', 'Gm30003', 'Acss1', 'Grem1', 'Nkd1', '1700018A04Rik', 'Kif26a', 'Fam107a', 'Pla2g7', 'Lhx9', 'Eya2', 'Akap12', 'Abtb2', 'Rgs5', 'Rbms3', 'Ankrd55', 'Qpct', 'Adamts16', 'Gabrq', 'Tead1', 'Gm29374', 'Col1a1', 'Amigo2', 'Lgr6', 'Wnt7a', 'Gm5089', 'Smco4', 'Gm49980', 'Lmo2', 'Ecm2', 'Gm39436', 'Fzd1', '1700063D05Rik', 'Ptpn13', 'Slc13a5', 'Calca', 'Cfap52', 'Usp43', 'Sypl2', 'Smyd2', 'Onecut1', 'Nxn', 'Tspan15', 'Dock11', 'Zim1', 'Cecr2', 'Foxq1', 'Smpdl3b', 'Trh', 'Plscr4', 'Gpr150', 'Akap7', 'Armc10', 'Ankrd34b', 'Nek7', 'B3galt5', 'Svil', 'Il16', 'Gm5089', 'Ocln', 'Ednra', 'Mndal', 'Serpina3n', 'Rasd1', 'Lama1', 'St8sia5', 'Slc9a2', 'Csdc2', 'Rnf141', 'Lacc1', 'Gm15825', 'Zan', 'Gm35835', 'Esyt3', 'Greb1', 'Ano5', 'Zfp521', 'Pde5a', 'Gm49767', 'Col10a1', 'Efna2', '5830418P13Rik', 'Slc39a12', 'Gm26644', 'Gm29771', 'Mycl', 'Crnde', 'Sec14l2', 'Tspan33', 'Ano10', 'Abcc4', 'Gm42722', 'Rragd', 'Gatm', 'Colec12', 'A830029E22Rik', 'Togaram2', 'Clrn1', '4930417O13Rik', 'Sntb1', 'Apbb1ip', 'Gm50048', 'Ano2', 'Gipc2', 'Mycn', 'Bhlhe41', 'Soat1', 'Gm42865', 'Ypel4', 'Podxl', 'Rab3d', 'Lrrc10b', 'Gm47163', 'Cdc34', 'Pim3', 'Gm13630', 'Gm47664', 'Rin1', 'Gm46102', 'Lor', 'Slc22a3', 'Mpdz', 'Dach2', 'Sowaha', 'Chgb', 'Gm34667', 'Elfn1', 'Cdk6', 'Hpgd', 'Scrt2', 'Gm42456', 'Ttc39b', 'Gm34921', 'Zfp57', 'Pkp2', 'Usp25', 'Gm6260', 'Far2os1', 'Ptgs1', 'Rccd1', 'Zfp467', 'Mab21l1', 'Cav1', 'Esr2', 'Iqsec3', 'Pth1r', 'Fam163a', 'Olfr316', 'Ankrd45', 'Pwwp3b', 'Pth2r', 'Btg1', 'Csrp1', 'Sox5os4', 'Ass1', 'Kank4', 'Nxph2', 'Isoc1', 'Dsc2', 'Gm6602', 'Fancd2', 'Emb', 'Ttc6', 'Slc17a8', 'Rab37', 'Tnfrsf11a', 'Pmp22', 'Aqp4', 'Pcnt', 'Ypel2', 'Gm14507', 'Ccdc60', 'Efemp1', 'Gm44618', 'Plxnc1', 'Retreg1', 'Slco2a1', 'Emx2', 'Pcsk9', 'Hectd2os', 'Gm34961', 'Cxadr', 'Htr1d', 'Tmem132c', 'Gm15997', 'Samd3', 'Mfap3l', 'Tmc1', 'Mc5r', 'Crlf1', 'Ankrd34c', 'Pthlh', 'Tpm2', 'Cenpa', 'Vangl2', 'Gm17231', 'Lrmp', 'Trnp1', 'Fam131b', 'Cdk19', 'Ucn', 'Zfp275', '2610307P16Rik', 'Gm17750', 'Tubb2b', 'Foxred2', '4933412O06Rik', 'Cnksr3', '9330154J02Rik', 'Pcgf5', 'Kcnq1', 'Pdgfa', 'Arid5b', 'Nek6', 'Bcor', 'Rapgefl1', 'Sec14l1', 'Shc3', 'Hs6st1', 'Btg2', 'Ptp4a3', 'Il34', 'Gm14066', 'Pole4', 'Rfk', 'Laptm4b', 'Gm19531', 'Gm39822', 'Adamtsl2', '4732419C18Rik', 'Tle4', 'Sgk3', 'Nrip1', 'Galnt13', 'Otud1', 'Ksr1', 'Ptch1', 'Wasf1', 'Prune2', 'Ece2', 'Smo', 'Lyn', 'Gm5087', '4921534H16Rik', 'Adamts13', 'Rph3al', 'Lima1', 'Gm45441', 'Aqp11', 'Kctd6', 'Tmem131l', 'Gm19938', 'Foxn3', 'Grk3', 'Fchsd2', 'Hmgcs1', 'Mfsd4a', 'A230057D06Rik', 'Rgs14', 'Epb41l3', 'Irs2', 'Cadm4', 'Gpx1', 'Fscn1', 'Slco3a1', 'Cul4a', 'B4galt6', 'Limd2', 'Rap2b', 'Zfyve28', 'Fgf13', 'Nrxn2', 'Gm10076', 'Ablim2', 'Fmnl2', 'Rab40b', 'Fndc4', 'Msi2', 'Cacnb3', 'Tuba1a', 'Cdk5r2', 'Kpna1', 'Ncan', 'Zfp697', 'St3gal5', 'Nap1l5', 'Specc1', 'Sort1', 'Slc16a7', 'Rab15', 'Srrm4', 'Klf6', 'Sh3bgrl', 'Arhgef25', 'Tmem121b', 'Arl4a', 'Faah', 'Icam5', 'Scn3a', 'Mir9-3hg', 'Kcnk1', 'Rgl1', 'Sprn', 'Cers6', 'Luzp1', 'Mrtfb', 'R3hdm4', 'Pgm5', 'Bmp6', 'Gng10', 'Sdccag8', 'Gfod1', '5330434G04Rik', 'B230334C09Rik', 'Map7', 'Pak3', 'Smarca2', 'Gucy1b1', 'Scn2b', 'Camk2b', 'Unc80', 'Mmd', 'Ahcyl2', 'Eno2', 'Ptprn2', 'Itm2c', 'Synj1', 'Impact', 'Ppp3ca', 'Ywhaz', 'Cacna1c', 'Frmd4a', 'Nat8l', 'Klhl29', 'Serp2', 'Map2k1', 'Atp1a3', 'Cnnm1', 'Pkig', 'Sobp', 'Fam171b', 'Ndrg3', 'Ahi1', 'Scn8a', 'Cend1', 'Astn2', 'Pdha1', 'Ncdn', 'Gpm6a', 'Cdr1os', 'Csrnp3', 'Ttll7', 'Dpp6', 'Crmp1', 'Rnf150', 'Tubb3', 'Sez6l2', 'Lpgat1', 'Tspan18', 'Kl', 'Nkd2', 'Golm1', 'Ankrd29', 'Prox1', 'Pax6', 'Gad2', 'Glce', 'Vwa5b1', 'Hopx', 'Syce2', 'Spink8', 'Moxd1', '4930452B06Rik', 'Dgkk', 'Arhgap36', 'Stk32b', 'C1qtnf7', 'Fn1', 'Cdc14a', 'Peg10', 'P3h2', 'Gpc3', 'Lefty1', 'Gpr161', 'Gm11906', 'C1ql2', 'Vcl', 'Kdr', 'Fbln1', 'Fam210b', 'Nhsl1', 'Serpina3g', 'Ptprc', 'Gm5535', 'Gm30094', 'Olig3', 'Siah3', 'Ipmk', 'AW551984', 'Hmgn5', 'Frem1', 'Synpo2', 'Zic2', 'Calcrl', 'Myof', 'Ctbp2', 'Nova1', 'Dennd1b', 'Zbtb46', '4930483P17Rik', 'Pkd1l3', 'Cgn', 'Gm20501', 'Ltk', 'P2ry14', 'Glp1r', 'Klhl4', 'Gm34045', 'Cobll1', 'Ube2cbp', 'Grxcr2', 'BC046251', 'Cklf', 'E430024P14Rik', 'Cdkl1', 'Smc2', 'Grhl1', 'Cd36', 'Ick', 'Pcsk6', 'Syne2', 'Tex14', 'Mro', 'Tbc1d8b', 'Epb41l4a', 'Il33', 'Rab34', 'Gm15261', 'Atp11c', 'Sipa1l3', '6330420H09Rik', 'Vmn1r206', 'Tex15', 'Gm34719', 'Creb3l2', 'Ppp4r4', 'Tbata', 'Gm31592', 'Gm28320', 'Gldn', 'Col13a1', 'Arhgef10', 'Tppp3', 'Fmo1', 'Col6a3', 'Gm12840', 'Klhl5', 'Rxfp3', 'Bc1', 'Igdcc4', 'Sst', 'Gm35041', 'Galr1', 'Rhoj', 'Tmem26', 'Ppp1r17', 'Npbwr1', 'Kcnk3', 'Arhgef3', 'Kctd12b', 'Gjc1', 'Sox2', 'Lncenc1', 'Pls1', 'Gm12536', 'Ucma', 'Vwa5b2', 'Plekhb1', 'Aldh3b2', 'Atp1a2', 'Mapk11', 'Gucy2g', 'Shisa2', 'Kyat1', 'Glipr1', 'Nsmce3', 'Prkch', 'Gm49708', 'Gm41361', 'Myo6', 'Scarb1', 'Skap2', 'Gm19757', 'Gm17276', 'Chodl', 'BC051537', 'Capn3', 'Atp6v1c2', 'Gm45847', 'Rwdd3', 'Gm34006', 'Rnf207', 'Bcan', 'Klk8', 'Anln', 'Simc1', 'Drd5', 'Egfl6', 'Lct', 'Cldn10', 'C630043F03Rik', 'Rara', 'Depdc7', 'Lingo3', 'B230110G15Rik', 'Hist1h2bc', 'St8sia6', 'Lrp2', 'Cfap100', 'Car8', 'Tnni3k', 'Zfp516', 'Insyn2a', 'B530045E10Rik', 'Rhobtb1', 'A630012P03Rik', 'Irf8', 'Tekt1', 'Pdcl', 'Flt3', 'Gm49969', 'N4bp3', 'A430010J10Rik', 'Gm36431', 'Spata6', 'Pmfbp1', 'Megf6', 'Myo10', 'Cd55', 'Narf', 'Nr1d1', 'Trim17', 'Ccdc177', 'Mrgpre', 'Acot2', 'Sstr3', 'Plpp6', 'Kcns3', 'Plppr5', 'Mpp7', 'Rsu1', 'Katnal2', 'Trim36', 'Gpr139', 'Mthfd1l', 'Aifm3', 'Napepld', 'H2-D1', 'Ngfr', 'H2-K1', 'Cdc25c', 'Fdft1', 'Kcnh8', 'Mreg', 'Acot1', 'Stra6', 'Apela', 'Vmn2r85', 'Tmem241', 'Col6a2', 'Ramp2', 'Fzd8', 'Stc2', 'Plod2', 'Pcdh18', 'Spink13', 'Gm29683', 'Prox1os', 'Il6ra', 'Mcub', 'Pcca', 'Gas6', 'Creb3l1', 'Fndc3b', 'Tnfrsf23', 'Klf14', 'Sstr1', 'Crem', 'Dubr', 'Gm20713', 'Gm43434', 'Slc2a9', 'Bag3', 'Ddc', 'Gm35040', 'Cdc14b', 'Spef2', 'Mmp15', 'Gm31816', 'Hmgb3', 'Rnf217', 'Teddm2', 'Slc16a6', 'Arhgdib', 'Dennd2a', 'Pld1', 'Agbl1', 'Gja3', 'Daam2', 'Endod1', 'Aph1b', 'A930029G22Rik', 'Gm13832', 'Fam241a', 'Jade2', 'Eps15', 'Nmbr', 'Zbbx', 'Homer3', 'D7Ertd443e', 'Ifi203', 'Gjd2', 'Extl2', 'Armc4', 'Krt5', 'Slc15a2', 'Cebpa', 'Itpr2', 'Gdf10', 'Gm9885', 'Tbc1d2b', 'Dusp4', 'Art3', '2310001H17Rik', 'Myrf', 'Ryr1', '5330429C05Rik', 'B430212C06Rik', 'Gm44812', 'Abca1', 'Ermn', 'Cth', 'Vstm5', 'Irs4', 'Kcnj12', 'C1galt1', 'Nog', 'Arl5b', 'Gcnt1', 'Pappa2', 'Fam107b', 'Trappc3l', 'Cdk2ap1', 'March11', 'Magel2', 'Pck2', 'Rab8b', 'Cyb561', 'Abcb1b', 'Rem2', 'Vps13c', 'Itm2a', 'Arhgap22', 'Il17rd', 'Tcf15', 'Amot', '1700017B05Rik', 'Kbtbd11', 'Sptb', 'Slc9a4', 'Cbwd1', 'Wwc2', 'Ndn', 'Pgap1', 'Efr3b', 'Prkag2', 'Klhl2', 'Zswim6', 'Kcnab2', 'Sim1', 'Pip4k2c', 'Stmn4', 'Mamld1', 'Syt5', '9630028H03Rik', '6330411D24Rik', 'Shisa8', 'Mcu', 'Gm26760', 'Sh3bp5', 'Qk', 'Mtfp1', 'Coro2b', 'Rit2', 'Osbpl6', 'Rnf227', 'Kif21a', 'Tmem130', 'Ptprn', 'Sik3', 'Bag1', 'Bex1', 'Dock9', 'Foxp1', 'Klhl3', 'Hspa12a', 'Usp22', 'Trim2', 'Add2', 'Tcaf1', 'Pnmal1', 'Nmnat2', 'Disp2', 'Otx1', 'Lratd2', 'Erg', 'Chrna6', 'Vsig2', 'Chrnb3', 'Ctxn3', 'Teddm3', '1810034E14Rik', 'Nxph4', 'Galnt10', 'Tmem40', 'Shb', 'Clcn2', 'Stk17b', 'Gm26673', 'Prph', 'Cfap58', 'Pvalb', 'Bche', 'Cdh23', 'Itga1', 'Pakap', 'Atp10b', 'Klhl33', 'Igdcc3', 'Scara3', 'Lipm', 'Gm42707', 'Il22', 'Iltifb', 'Spc25', 'Egflam', 'Bend7', 'Oma1', 'Ntsr2', 'Glp2r', 'Tsc22d3', 'Cast', 'Tnfaip8', 'Tspan12', 'Kif6', 'Pou2f2', 'Cybrd1', 'Rcn3', 'P2rx5', 'Kcnk10', 'Stk26', 'Cd109', 'Iyd', 'Skida1', 'Ankrd37', 'Spry4', 'Gm48007', 'Icosl', 'Tuba8', 'Mfsd13b', 'Actn2', 'Catsperz', 'Fgf5', 'Lnx1', 'Mcur1', 'Fam181b', 'Ccdc88b', 'F2r', 'Egfr', 'Plekhd1', 'Shisal2b', 'Tead4', 'Ltbp3', 'Gsap', 'Gpr137c', 'Rapgef4os1', 'Glcci1', 'Esm1', 'Arhgap28', 'Kcng3', 'Krt77', 'Far2', 'Fkbp5', 'Gm11730', 'Gm35853', 'Sult5a1', 'Zfp827', 'Cldn34c1', 'Prcp', 'Gm44593', 'Eng', 'Hk2', 'Rhobtb3', 'Trim66', 'Gm41322', 'Pmaip1', 'Mc4r', 'H2-Q2', 'Adamts19', 'A730056A06Rik', '9330159M07Rik', 'Ptgfr', 'Arl14ep', 'Tmem100', 'Tcf7l1', 'Pcdhb20', 'Bmp5', 'Sema3f', 'Arhgap29', 'Ccdc192', 'Asah2', 'Kcnn1', 'Gm36543', 'Tecta', 'Proser2', 'Etv4', 'Papln', 'Cort', 'Ccdc112', 'Krt80', 'Gm15663', 'Podn', 'Gm40493', 'Arg2', 'Qrfprl', 'Eya4', 'Gm31045', 'Steap3', 'Parvg', 'Sebox', 'Dnajc15', 'Dzip1', 'Thbs1', 'Hnmt', 'Fgd2', 'B230206L02Rik', 'Cd164l2', 'Krt73', 'Glyat', 'Jag1', 'Tm4sf1', 'Gm13936', 'Sod3', 'Cela1', 'Cda', 'Gm44257', 'Cmtm4', 'Gm16062', 'Gm26604', 'Tmem144', '1810010H24Rik', 'Erich3', 'Loxl1', 'Cldn22', 'Dbndd1', 'Dnaja4', 'Pxn', 'Mafa', 'Ttn', 'Otos', 'Arvcf', 'Fxyd5', 'Asic1', 'Rasgrp4', 'Cntfr', 'Slc7a4', 'Map3k15', 'Frmpd1', 'Fgf16', 'Mis18a', 'A330070K13Rik', 'Gm48992', 'Olfr111', 'Rasa4', 'Fkbp9', 'Smpd3', 'Shtn1', 'Lonrf1', 'Me1', 'Adam11', 'Sorbs1', 'Setbp1', 'Ssbp2', 'Cnih2', 'Slc1a1', 'Grin1', 'Asph', 'Selenom', 'Sms', 'Pclo', 'Sept3', 'Cpe', 'Herc3', 'Stxbp1', 'Limk1', 'C330002G04Rik', 'Itga5', 'Sptbn5', 'Raet1e', 'Glul', 'Col5a1', 'Shisa5', 'Il11ra1', 'Prdm5', 'Irak2', 'Traip', 'Skap1', 'BC025920', 'Atf5', 'Chrna5', 'Cd164', 'Clic5', 'Pirt', 'Filip1l', 'Kcnj2', 'Arl4d', 'Gad1', 'Abhd3', 'Dsp', 'Ror2', 'Abcd4', 'Fam110b', 'Gm48742', 'Lefty2', 'Stambpl1', 'Rsph10b', 'Rasgrp3', 'Spaar', 'Snx9', 'Rnd1', 'Dip2a', 'Slc4a7', 'Dlg5', 'Lrrc1', 'Gm13391', 'Pakap', 'Dlx6os1', 'Htr3a', 'Slc32a1', 'Npas1', 'Dlx1', 'Gm39185', 'Gm11713', 'Vip', 'Dlx1as', 'Tac2', 'Rpp25', 'Sult2b1', 'Srxn1', 'Atf3', 'Gm42477', 'Acan', 'Mir22hg', 'Plekhg5', 'Prrt3', 'Dact1', 'Vrk1', 'Myom1', 'Wnt5b', '9430014N10Rik', '0610040J01Rik', 'Gm30564', 'Sergef', 'Tnmd', 'Phldb2', 'Pik3r5', 'Thbs2', 'Epas1', 'Kynu', 'Pstpip2', 'Myh3', 'Psd4', 'A630023P12Rik', 'Vldlr', 'Ahnak', 'Itpk1', 'Gm43066', 'Abca9', 'H2-T22', 'Kcnmb4os2', 'Nrip2', 'Aig1', 'Wdr95', 'Cd68', 'Dtx4', 'Dlgap3', 'Mblac2', 'Rwdd2a', 'Adam23', 'Gm46367', 'Gm17202', 'Eno1', 'Tubb4b', 'Gm39377', 'Zfp948', 'Myh9', '1810030O07Rik', 'Tacc2', 'Ier2', 'Per1', 'Cebpb', 'Entpd7', 'Gm49542', 'Gm31615', 'Sesn1', 'Spata7', 'Gpr85', 'Mtus2', 'Fyco1', 'Slc25a27', 'D630045J12Rik', '2210408F21Rik', 'B230217O12Rik', 'Pnoc', 'Sncg', 'Has2os', 'Haus8', 'Gm4211', 'Tmem176a', 'Tmem176b', 'Trim46', 'Dagla', 'Vwa3b', 'Slc26a10', 'Il1r1', 'Tmem175', 'Cpox', 'Snhg20', 'Gal3st3', 'Ttc26', 'Gm9828', '4732463B04Rik', '1810013L24Rik', 'Atad1', 'Efna3', 'Amer3', 'Slc6a15', 'Gm43847', 'Sox1ot', 'C79798', 'Npffr1', 'Gdpd2', 'Ccdc74a', 'Zfp710', 'Surf4', 'Nr2e1', 'Bcar3', 'Myo3b', 'Aif1', 'Susd2', 'Emx1', 'Tmem128', 'Snai2', 'Tbc1d2', 'Acaa1b', 'Adora2a', 'Nkx1-2', 'Anxa4', 'Ifitm2', '1700080G11Rik', 'Urah', 'Myzap', 'Sla2', '4930598N05Rik', 'Mtss2', 'Pln', 'Ifi27l2a', 'Snorc', 'Prkcq', 'Fgd6', 'Gm17634', 'Lrp12', 'Ngrn', 'Acvrl1', 'Hist1h1c', 'Gm12295', 'Hapln1', 'Fra10ac1', 'Ndufaf3', 'Mrpl14', 'Gm34184', 'Rac3', 'Cyb5r1', 'Hmga2', 'Plxnb1', 'Zyx', 'B4galnt3', 'Ppp1r18', 'Fxyd2', 'Olfr110', 'Lair1', '5031425F14Rik', 'Rhoc', 'Chmp4c', '5033421B08Rik', 'Gm47902', 'Crybg1', 'Nipal2', 'Gli2', 'Gm45904', 'Igsf10', 'Usp3', 'Aox3', 'Enox2', 'Gse1', 'C7', 'Grpr', 'Sdc2', 'Rgmb', 'Bend4', 'Klf7', 'Prkd3', 'Stk32a', 'A730020E08Rik', 'D030055H07Rik', 'Mns1', 'Entpd1', 'Prxl2a', 'Gpr149', 'Msrb2', 'Prkar2b', 'Adgrb2', 'Slc20a1', 'Prkn', 'Atp6ap2', 'Ptk2', 'Cd47', 'Dtna', 'Enho', 'Gm14204', 'Arx', 'Klf13', 'Gm38505', 'Rap1gds1', 'Ppp2r5a', 'Ogfrl1', 'Abr', 'Scai', 'Bmerb1', 'Arhgap44', 'Pkp4', 'Rab6a', 'Tspan7', 'Lncpint', 'Kdm7a', 'Ift57', 'Ets2', 'Grin2d', 'Hspa4l', 'Ptprj', 'Sgip1', 'Rasal2', 'Plcl2', 'Arpc5', 'Col14a1', 'Scrg1', 'Sp8', 'Slc5a7', 'Mob3b', 'Yjefn3', 'Lhx6', 'Afap1', 'Sln', 'Clic4', 'Megf10', 'Myl1', 'Gm45321', 'Ddr2', 'Sox1', 'Prok2', 'Gm42303', 'Cp', 'Sp9', 'Spx', 'Gm49227', 'Slc10a4', 'Pag1', 'Gm16070', 'Edaradd', 'Itih5', 'Gm3510', 'Tnnt1', 'Creb5', 'Ostf1', 'Chat', 'P2ry1', 'Hip1', 'Bex4', 'Maoa', 'Hpse', 'A330093E20Rik', 'Psat1', 'Arhgef37', 'Nmrk1', 'Ret', 'Fryl', 'Polr1d', 'Nedd9', 'Sh2d5', 'Gm15345', 'Edn3', 'Traf6', 'Id3', 'Eif5a2', 'Usp2', 'Gnaz', 'Tpd52', 'Pkia', 'Ppp1r1c', 'Tmem123', 'Pou3f4', 'Dusp10', 'Dock5', 'Heg1', 'Ptgds', '2810468N07Rik', 'Tbc1d4', 'Tgfbi', 'Fam174b', 'Srebf2', 'Mtmr6', 'C2cd2l', 'C87487', 'Baiap2l2', 'Nt5e', 'Slc35d3', 'Aqp5', 'Fgfr3', 'Phlpp1', 'Sgms1', '4930415C11Rik', 'Tph2', 'Slc39a11', 'D030045P18Rik', 'Cftr', 'Ints6l', 'Far1', 'Gss', 'A830019P07Rik', 'Pdgfra', 'Gm9962', 'Sdc3', 'Frem2', 'Ripk2', 'Ggct', 'Sytl5', 'Nfkbiz', 'Ahrr', 'Gsto1', 'Larp1b', 'Intu', 'Crabp1', 'Arid5a', 'Cyp1b1', 'Gm36529', 'Ets1', 'Slc41a1', 'Fgd5', 'Mid1', 'Agtr1a', 'Ophn1', 'Tcim', 'Slc30a10', 'Rnf130', 'Dio2', 'Gm30373', 'B020031H02Rik', 'Sfta3-ps', 'Nkx2-1', 'Calcb', 'Myh8', 'Adam28', 'Itgb6', 'Tnc', 'Padi2', 'Gas2l3', 'Wdr49', 'Frmd7', 'Ano1', 'Cdca7l', 'Sytl4', 'Pdzph1', 'Lrguk', 'Rarres1', 'Gm31218', 'Wif1', 'Gm35657', 'Gm26512', 'Mmp14', 'Ibsp', 'Dytn', 'Pola1', 'Cdyl', 'Bmp4', 'Slc18a2', 'Kcnq4', 'Snx31', 'Gm20559', 'Fam114a1', 'Ldoc1', 'Slco5a1', 'G0s2', 'Phgdh', 'Tchh', '9330179D12Rik', 'Dhrs7', 'Sesn2', 'Plekhh1', 'Asb4', 'Cfap77', 'Fzd5', 'G630018N14Rik', '9430021M05Rik', 'Pgf', '9330188P03Rik', 'Sall1', 'Pllp', 'Rbpj', 'Nupr1', 'Pcnx2', 'Ccdc71l', 'Tmem45a', 'Lrrc38', 'Selenov', 'Adamts15', 'Nt5dc2', 'Hmbox1', 'Plekha6', 'Itgad', 'Gm28153', 'Prom1', 'Gm13112', 'Mpst', 'Nr1h4', 'Slc22a23', 'Ddt', 'Slc7a3', 'Gm15503', 'Macrod1', 'Slitrk5', 'Pdlim3', 'Adamts12', 'Ccsap', 'C230057M02Rik', 'Apba1', 'Bcl9', 'Fabp5', 'Mxd4', 'Tbc1d30', 'Ano6', 'Cacna1b', 'Insyn1', 'Manea', 'Ppp1r14b', 'Lrrc4', 'Gm48321', 'Vwa5a', 'Ostm1', 'Diras1', 'Dcaf17', 'Scrt1', 'Tbl1xr1', 'Dlx6', 'Dlx2', 'Ctnnbip1', 'Trerf1', 'Scrn1', 'Elfn2', 'Cdk17', 'C1qtnf4', 'Atxn1', 'Pnma2', 'Smim26', 'Inpp5f', 'Snhg14', 'Cbarp', 'Dennd5b', 'Uhmk1', 'Crhbp', 'Corin', 'Th', 'Aga', 'Myl6b', 'Timm8a1', 'Ahr', 'Nipsnap3b', 'Slc7a5', 'Gna14', 'Ache', 'Crhr2', 'Prdm1', 'Anxa2', 'Selenop', 'Cxcr4', 'Gm15417', 'St6galnac2', 'Cdca7', 'Gm2464', 'Ifit1', 'Platr14', 'Dmrt2', 'Chrna2', 'Wnt16', 'Spsb4', 'Myh13', 'Myh4', 'Paqr5', '4930544I03Rik', 'Spp1', 'Efnb1', 'Dgcr6', 'Akr1c18', 'Cdk15', '2610028E06Rik', 'Slc25a13', 'Timeless', 'Pla2g5', 'Dab2', 'Shroom4', 'Oasl2', 'Tst', 'C230034O21Rik', 'Zc3h6', 'Rbp1', 'F830208F22Rik', '1700001L19Rik', 'Cnn3', 'Emilin2', 'Rxra', 'Chac1', 'Eml1', 'A730009L09Rik', 'Mageb18', 'Ccna1', 'Ifit3', 'B3gnt2', 'Adamts20', 'Sema6c', 'Klf8', 'Rtkn2', 'Gm11837', 'Cdc42ep5', 'Inpp5j', 'Fgd3', 'Gm28756', 'Mypn', 'Dap', 'Adamtsl5', 'Kcng4', 'Kcns1', 'Adamts8', 'Stard9', 'Fam129a', '2010001A14Rik', 'Adm', 'Gm16685', 'Il7', 'Fam189a2', 'Gm48893', '9230114K14Rik', 'Palld', 'Zadh2', 'Elovl7', 'Gpnmb', 'Gm15723', 'Msrb3', 'Slc39a8', 'Pla2g4a', 'Ap1s3', 'Ostn', 'Spata1', 'Tmem41a', 'BC035947', 'Entpd3', '4930470O06Rik', 'Edn1', 'Sag', 'Dlx5', 'Tigar', 'Vipr2', 'Pdgfd', 'Tmem151b', 'Kcnc3', 'Phka2', 'Btk', 'Rpe', 'Celf5', 'Snhg4', 'Sbk1', 'Traf3', 'Rims4', 'Pacrg', 'Slc25a5', 'Cerk', 'Ldhb', 'Fnip2', 'Cdh2', 'Bend6', 'Got1', 'Lrp11', 'Gbx1', 'Lhx8', 'Casz1', 'Meis1', 'A730046J19Rik', 'Zic4', 'Six3', 'Slc18a3', 'Ntrk1', 'Isl1', 'Slc25a1', 'Ly75', 'Adgrf5', 'Gprasp2', 'Prima1', 'Nox4', 'Pdcl3', '9330182L06Rik', 'B630019K06Rik', 'Acly', 'Hdac11', 'Gm12068', 'Gm45680', 'Gbx2', 'Gpr156', 'Mylip', 'Pbxip1', 'Carhsp1', 'Fli1', 'Glra1', 'Flywch2', 'Nr5a2', 'Dock1', 'Gpr174', 'Gal', 'Cckar', 'Fam78b', 'Tln2', 'Shh', 'Fam222a', 'Acacb', 'Ccdc171', 'Lamc3', 'Gm38413', 'Pcbd1', 'Prkaa2', 'Gm40663', 'Drd3', 'Trdn', '4930547E14Rik', 'Sctr', 'Gm15584', '4932435O22Rik', 'Ebf4', 'Tmem72', 'Rassf4', 'Myc', 'Agmat', 'Kcnj5', 'Mcf2', 'Tmem25', 'Mboat1', 'Cyyr1', 'Ptar1', 'Gm13944', 'Plpp2', 'A830011K09Rik', 'Gzmk', 'D130058E05Rik', 'Cpa2', 'Epha8', 'Tnnt2', 'Dok4', 'Dynlt1a', 'Stk33', 'Gm12130', 'Gm12128', 'Dipk1c', 'Stx11', 'Cpq', 'Insig1', 'Gpr50', 'Gm27008', 'Gm12239', 'Snhg18', 'Scgn', 'Tafa4', 'Sec14l5', 'Chrna3', 'S100a11', 'Cd79a', 'Rspo4', 'Six3os1', 'Hcrtr1', 'Vwa7', 'Gpx2', 'Krt19', 'Mc3r', 'Angptl7', 'Dapl1', 'Gm47524', 'Gm44148', 'Nid1', '4933400L20Rik', 'Hmcn2', 'A330015K06Rik', 'Itprid2', 'Pkdcc', 'Fgf18', 'Mettl11b', 'Gm26633', '4933432K03Rik', 'Chrnb4', 'Tgm2', 'Rimklb', 'Pdhx', 'Armc9', 'Hspb8', 'Wipi1', 'Frem3', 'Ugt8a', 'Svbp', 'Tbc1d31', 'Avpr1a', 'Gm9934', 'Alox8', 'AI606473', 'Wipf1', 'Tmem28', 'Gm26839', 'Stox1', 'Cyp26a1', 'Frrs1', 'Dhdh', 'Gm20712', 'Pgr15l', 'Gm12296', 'Zar1', 'As3mt', 'Serpinb1b', '4833423E24Rik', 'Gm11250', 'Npffr2', 'Gadl1', 'Ier5l', 'Prim2', 'Gm45682', '2900079G21Rik', 'Ptgdr', 'Stard4', 'Gm26658', 'Dnah7b', 'Tmem200c', '4930587E11Rik', 'B230217J21Rik', 'Rffl', 'Gm13429', 'Gm48091', 'Cfap61', 'Col6a5', 'Tril', 'Gm38101', 'Nucb2', 'Perp', 'Insm1', 'Spag17', 'Nelfcd', 'Fank1', 'Gck', 'Lrrc42', 'Agtr2', 'Cabcoco1', '1110015O18Rik', 'Zdhhc24', '8430419K02Rik', 'Myo19', 'Rras2', 'Gm10421', 'Egfl7', 'Ccn1', 'Adamtsl3', 'Gm14114', '4930588J15Rik', 'Rttn', 'Idi1', 'Slitrk3', 'Pxylp1', '5033406O09Rik', 'Podxl2', 'Lbhd2', 'Trap1a', 'Cdh3', 'Gstm6', 'Olfr324', 'Gstm7', 'Coro2a', 'Smim17', 'Fhit', 'Ufsp1', 'Asrgl1', 'Epb41l1', 'Gstm1', 'Rai2', 'Zfp385a', 'Higd1a', 'Pik3r3', 'Coprs', 'Tnfrsf21', 'Nlgn3', 'Pip4k2a', 'Irgq', 'Fdps', 'Dhcr24', 'Nrbp2', 'Armcx3', 'Bmp7', 'Cep128', 'C78859', 'AI413582', 'Tnrc18', 'Minar2', 'Sybu', 'Clvs1', 'Slc25a12', 'Adgrl1', 'Gaa', 'Peg3', 'Psmc5', 'Mllt3', 'Slc38a1', 'Rell2', 'Tpi1', 'Syngr3', 'Dzank1', 'Ndufb5', 'Trappc2l', 'Stx1b', 'Nudc', 'Gnl3l', 'Slc23a2', 'Akap6', 'Tmem256', 'Nudt19', 'Pithd1', 'Shisa7', 'Sec61b', 'Celf3', 'Phyhipl', 'Adgrv1', 'Calcr', 'Impg1', 'Sh3rf2', 'Clic6', 'Fmod', 'Gli3', 'Phex', 'Prdm16', 'Prdm12', 'Mdfic', 'Gm45159', 'Gpr6', 'Gm39043', 'Slc12a8', 'Gm15810', 'Hsd17b12', 'Foxp4', 'P2ry10b', '1700013H16Rik', 'Pantr2', 'Asb18', 'Gdnf', 'Gm15691', 'Dok7', 'Gpr39', 'Txlnb', 'Gm29478', 'Crabp2', 'Tmem114', 'Slco4c1', 'Bvht', 'Gm4117', 'Atp8a2', 'Snrnp25', '6430628N08Rik', 'Appl2', 'Gm9725', 'C230014O12Rik', 'Agpat4', 'Fgd4', 'Cfap206', 'Upk1b', 'C87436', 'Pifo', 'Fam117a', 'Gm16638', 'A830012C17Rik', 'Itga11', 'D130043K22Rik', 'Zfp961', 'Glrx', 'Slc17a5', 'Fam122b', 'Klhl24', '5330417C22Rik', 'Arhgap17', 'Gls', 'Gm38575', 'Mhrt', 'Gm10165', 'Asb11', 'Slitrk6', 'Fa2h', 'Gm42439', 'Zkscan16', 'Slc38a6', 'Kdsr', 'Krt222', 'Cdc25b', 'Brca1', 'Lipa', 'Kcna5', 'P4ha3', 'Rsph4a', 'Slc1a4', 'Serpina9', 'Gm31251', 'Prxl2c', 'Gm16894', 'Cd4', 'Acer3', 'Rbm11', 'Mfge8', 'Fig4', 'Lrrc9', 'Gm33651', 'Dlk2', 'Lgr4', 'Sh3pxd2a', 'Ikzf4', 'Upb1', 'Cdo1', 'Scn10a', 'Atp13a5', 'Efcc1', 'Gm12703', 'Lrmda', 'Gem', 'Stk10', 'Gm10851', 'Agbl2', 'Dse', 'Gm10714', 'Serpinb2', 'Gja5', 'Dsg1c', 'Sfxn1', 'Npl', 'Ctnna1', 'Usp28', 'Gm50370', 'Kank3', 'Gm30313', 'Zp3r', '9230009I02Rik', 'Iglon5', 'Clspn', 'Cyp2s1', 'Tspear', 'Mdk', 'Strit1', 'Cd72', 'Gm28494', 'Gm6556', 'Mgst1', 'Gm31517', 'Gm36372', 'Ctss', '2810032G03Rik', 'Ido1', 'Cyp46a1', 'Gm26645', '4933431E20Rik', 'Gpr52', 'Angpt2', 'Insrr', 'Prr5l', 'Cd274', 'Ifngr2', 'Gm39456', 'Kif21b', 'Ptcd1', 'Ccdc187', 'Stk3', 'Pcdhb7', 'Decr1', 'Ralb', 'Ppp1r2', 'Folh1', 'Pros1', 'Gm35281', 'Gm12992', 'Hebp1', 'Zbed3', 'Sox13', 'Gm44643', 'Crebrf', 'Aim2', 'Hmgcll1', 'Zfp934', 'Tceal8', 'Fbxl21', 'Lrpprc', 'S100a16', 'Nrn1l', 'D830036C21Rik', 'Sat1', 'Vipr1', '1700003D09Rik', 'Nlrp10', 'D930020B18Rik', '1700001F09Rik', 'Gm29088', 'Gas1', 'Map3k1', 'Cemip2', 'Gpr45', 'Cystm1', 'Rab11fip4', 'Tank', 'Ivns1abp', 'Ephx2', 'Gm50024', 'Dbp', 'Coq10b', 'Zc3h12c', 'Pcsk2os1', 'Il20ra', 'Mospd2', 'Bbx', 'Ckb', 'Msantd4', 'Rap2a', 'Znrf1', 'Mbnl1', 'Gramd1b', 'Mbnl2', 'A330023F24Rik', 'Cox17', 'Map2', 'Wdfy3', 'Otx2os1', 'Nfatc1', 'Col9a3', 'Sall3', 'Otx2', 'Zic3', 'Gabre', 'A330076H08Rik', 'Fmc1', 'Ccdc30', 'Ccdc6', 'Cacng8', 'Inafm2', 'Gm41836', 'Selenoh', 'Arhgef38', 'Ttc23', 'Gm32815', 'Aard', 'Cntln', 'Bub1b', 'Acvr1', 'Grid2ip', 'Samhd1', '1500009C09Rik', 'Abcb10', 'Gm45025', 'Pax6os1', '4930473D10Rik', 'Phka1', 'Lrrc75b', 'B930025P03Rik', 'Maged2', 'Cmtm8', 'Cavin2', 'Styk1', 'Cytip', '4930414F18Rik', 'Cpeb1', 'Armcx6', 'Drp2', 'Ndp', 'Zfhx2', 'Sox3', 'Clvs2', 'Igsf1', 'Apold1', 'Doc2g', 'Enpp1', 'Mlc1', 'Slc14a2', 'Scx', 'Ttr', 'Itpr3', 'Chrne', 'Gm12315', '4933428C19Rik', 'Ikbip', 'Gpr4', 'Cyth1', 'Map2k3', 'Srgap2', 'Rad51ap2', 'Gm5577', 'Myt1', 'Tec', 'Cables1', 'Pawr', 'Notch4', 'Rbm8a2', 'Edar', 'Gm26618', 'Abcc8', 'Gk5', '4933413L06Rik', 'Nfatc2', 'Rgs11', 'Ccdc120', 'Bean1', 'Gramd4', 'Mpzl1', 'Cnn2', 'Scd1', 'Pard6g', 'Nup93', 'Mthfd2', 'Rbl1', 'Pon3', 'Tnfrsf8', 'Tpcn1', 'Gramd1c', 'Rec8', 'Bpgm', 'Naaa', 'Lrrc8c', 'Stat5a', 'Tmem266', 'Lamb3', 'Cyfip1', 'Cfap97d2', 'Cfap45', 'Klhl8', 'Elovl2', 'Snta1', 'Nat14', 'Fam149a', 'Mak', 'Slc9a7', 'Rfx4', 'Gm2379', 'Phf11d', 'Rilp', 'A930001A20Rik', 'Sdcbp2', 'Irf6', 'C230038L03Rik', 'Myo1h', 'Suclg2', 'Prrxl1', 'Gm37892', 'Npy5r', 'Zdhhc15', 'Pgpep1l', 'Zfpm1', 'Fbxo17', 'Ern1', 'Zfp711', 'Tcp11l2', 'Pgr', 'Dyrk2', 'Mettl8', 'Tmem132cos', 'Htr5b', 'Clybl', 'Gm28221', 'Ndufa11', 'Swap70', '4930570G19Rik', 'Epsti1', 'Ctnnbl1', 'Bmyc', 'Extl1', 'Chrna10', 'Slc4a8', 'Aldh1l2', 'Vegfa', 'B830012L14Rik', 'Col4a2', 'Serpinf1', 'Anxa10', 'Emx2os', 'Slc7a1', 'Phyh', 'Nynrin', 'Kif13a', 'Actr3b', 'Hdx', 'Otulinl', 'Spata2l', 'Sp3os', 'Zswim5', 'Focad', '1700025G04Rik', 'Ptp4a2', 'Apbb2', 'Astn1', 'Rap1gap', 'Rundc3b', 'Nme2', 'Atp9a', 'Trio', 'Lrrfip1', 'Ramac', 'Nalcn', 'Rangap1', 'Mllt11', 'Mirg', 'Pmm1', 'Tmem191c', 'Dst', 'Ncs1', 'Ndufs4', 'Cltb', 'Cbx6', 'Cdc42bpa', 'Dlg3', 'Enah', 'Jazf1', 'Elavl3', 'Nexmif', 'Tcf7l2', 'Shox2', 'Trpm6', 'Gpr151', 'Pou4f1', 'D130009I18Rik', 'D130079A08Rik', 'Syt15', 'Nppa', 'Nhlh2', 'Nfam1', 'Gm32828', 'Vangl1', 'Ptprq', 'D930028M14Rik', 'N4bp2', 'Ptpdc1', 'Ebf3', 'Cngb3', 'Irx2', 'Eps8l2', 'Cnnm2', 'Ing2', 'Slco1c1', 'Gm32255', 'Ccdc190', 'Cyth4', 'Eva1c', 'Pik3c2g', 'Lrp4', 'Mogat1', 'Gm27151', 'Fabp7', 'Dsel', 'Rab3ip', 'Fgf3', 'Avpi1', 'Gm49046', 'Prps2', 'Fzd10', 'Ezr', 'Dapp1', 'Ccnd3', 'Zfhx2os', 'Gm47153', 'Fbxw13', '6430590A07Rik', 'Slc9a3r1', 'Gm13373', 'Col8a2', 'Bcr', 'Tnfaip2', 'Npr1', 'Wfikkn2', 'Riiad1', 'Dnah7a', 'Ccdc155', 'Sned1', 'Spred3', 'Dnah7c', 'Aebp1', 'Gm13269', 'Zfp976', 'Col16a1', 'Col5a3', 'Pcx', 'Mab21l2', 'Tagln2', 'Cubn', 'Gm20234', '4930545L23Rik', 'Hspb6', 'Lhfpl1', 'Rbp7', 'Gm11266', 'Dnaic2', 'Egf', '4930517O19Rik', 'Hdac7', 'Brip1', 'Sh3bp1', 'Pla2r1', 'Calhm5', 'Pdzd8', 'Impa2', 'Tuft1', '4930567K20Rik', 'Msi1', 'L3mbtl3', 'Zdhhc18', 'Umodl1', 'Gm38534', 'Ece1', 'Adam15', 'Tle2', 'Mrvi1', 'Gdf11', 'F13a1', 'L1cam', 'Thbs4', 'Enkur', 'Ecrg4', 'Cxcl13', 'Esrra', 'Twist1', 'Asb13', 'Gchfr', 'Gm28703', 'Cmbl', 'Fez2', 'Gm50431', 'Gm29521', 'Gab3', 'Abcg2', 'Onecut3', 'Epn3', 'Myh7b', 'Cuedc1', 'D030025E07Rik', 'Adra2b', 'Grtp1', 'Gm47352', 'Tnfsf13b', 'Avil', 'Nox1', 'Abhd12b', 'Cavin1', 'Ahnak2', 'Gulo', 'Gnai2', 'Grin2c', 'Myo5c', '4833411C07Rik', 'Acot7', 'Wnt3', 'Irx1', 'Axin2', 'Trmt2b', 'Col2a1', 'Cep112it', 'Bcam', 'Slc6a3', 'Gm40999', 'Ube2e3', 'Arel1', 'Nceh1', 'Rnf220', 'Dock7', 'Gabbr1', 'Nsmf', 'Ptpn4', 'Prkar2a', 'Srrm3', 'Map7d2', 'Adarb1', 'Slc29a1', 'Bnc2', 'Igkc', 'Inpp5a', 'Creg1', 'Gm28822', '9630028I04Rik', 'Fam20c', 'Wnt9b', 'Lrrc20', 'Dctd', 'Elk1', 'Gypc', 'Sprr2i', 'Pycr1', 'Cd247', 'Gm6213', 'Plcg2', 'Tom1l1', 'Fzd6', 'Fhdc1', 'St14', 'Epha1', 'Rcsd1', 'Zfp36l1', 'St3gal4', 'Defb1', 'Gm36520', 'Tmcc3os', 'F11r', 'Speg', 'Alpk2', 'Gtf2a1l', 'Adgrf2', 'Cryl1', 'Pafah1b3', 'Cd59a', 'Hs3st3b1', 'Aldh1a2', 'Cmtm7', 'Nmur2', 'Hs3st3a1', 'Fbln5', 'Slc25a37', '1700037H04Rik', 'Cdr2', 'Pde8a', 'Sptssb', 'Gm46563', 'Lmod2', 'Hspb1', '2010110G14Rik', 'Nans', 'Map6d1', 'Dusp27', 'Adgrf4', 'Sfxn2', 'Slfn9', 'Hpse2', 'Baiap2l1', 'Casq2', 'Ucp2', 'Osbpl5', 'Xylt2', 'Gm29865', 'Gm35696', 'Cd9', 'Ppp1r3a', 'Nde1', 'Zfp808', 'Cfap221', 'Asphd2', 'Atp2a1', 'Zfp114', 'Irf5', 'Eln', 'Cacna2d4', 'Snx20', '6720468P15Rik', 'Gm12082', 'Ctdspl', 'Gm31946', 'Kcp', 'Slc44a2', 'Tnfrsf12a', 'Kcne4', 'Smpx', 'Ecm1', 'Trim40', 'Cdr2l', 'Zfp385c', 'Slc16a12', 'Flt1', 'Elovl5', 'Car7', 'E2f1', 'Trp73', '9130017K11Rik', 'Efhd1', 'Ppard', 'Stil', 'Nod2', 'Bambi', 'Adam8', 'Psg16', 'Chek2', 'Hgsnat', 'Ccdc134', 'Per2', 'Rrad', 'Nin', 'Sh2d4b', 'Lgals3', 'Mtnr1a', 'Trdc', 'Arhgef5', 'Srpx2', 'Gm17171', 'Epb41l5', 'Sac3d1', 'Sertad4', 'Abhd8', 'Fkbp4', 'Stox2', 'Eomes', 'Avp', 'Lhx1os', 'Lhx1', 'Six6', 'Hdc', 'Bsx', 'Tbx3', 'Tesk2', 'Barhl2', 'Ms4a15', 'Tbx21', 'Ppm1j', 'Tfap2c', 'Vmn1r209', 'Cngb1', 'Diablo', 'Foxb1', 'B230323A14Rik', 'Gm5532', 'Pik3c2b', 'Pitx2', 'Postn', '4930438E09Rik', 'Fam184a', 'Cacng7', '6430710C18Rik', 'Gm34609', '1700023F06Rik', 'Kifc3', 'Slc22a5', 'Adipor2', 'Fzd7', 'Gnasas1', 'Tspan14', 'Fndc9', 'Msn', 'Sowahc', 'Dusp16', 'Plcd4', 'Tmem219', 'Ankrd24', 'Ammecr1', '1700111E14Rik', '5530401A14Rik', 'Lhx5', 'Platr21', 'Mal', 'Gm38560', 'Sycp2l', 'Gm48510', 'Hck', 'Gm12236', 'Gm12968', 'Tex2', 'Smtn', 'Nkx2-2', '3100003L05Rik', 'Gpld1', 'Ccnf', 'Klb', 'Slc12a7', 'Nms', 'Slc13a3', 'Brs3', 'Trank1', 'Mapkapk3', 'Sfrp4', 'Cited1', 'Plk4', 'Gfral', 'Gfra4', 'Arhgef2', 'Tmem51', 'Slc25a18', 'Atp8b5', 'Gm3985', 'Map3k19', 'C2cd4b', 'Pabpc1l', 'Gm16551', 'C230024C17Rik', 'Pir', 'Rnase4', 'Chil1', 'Ptrh1', 'Fzd4', 'Spag6l', 'Gm49890', 'Slc25a24', 'Fut2', 'Gm17396', 'Oas1c', 'Arntl', 'Dock8', 'Ghsr', 'Gm28782', 'Gm27199', 'Ghrh', 'Grap2', 'Gm28526', 'Itga2', 'Cox6b2', 'Anxa7', 'Gm32341', 'Gm32618', 'Gm48228', 'Gm32067', 'Prrx1', 'Sh3bgr', 'Angptl1', 'Pla2g3', 'Samsn1', 'Clic1', 'Tubb6', 'Vdr', 'Sgcg', 'Ss18', 'Gm45895', 'Ush1g', 'Mustn1', 'Tex9', 'Hpgds', 'Cyp2d22', 'Clu', 'Lsmem1', 'Sost', 'Ccl3', 'Rab26os', 'Hacd1', 'Tjp2', '1700120O09Rik', 'Mmp24', 'Cables2', 'Thbs3', '9330117O12Rik', 'Gm32885', '4930445B16Rik', 'Csta2', 'Uncx', 'Slc22a15', 'Kcnh2', '9130410C08Rik', 'Foxd2os', 'Rcc2', 'Rps6ka6', 'Duox2', 'Itsn2', 'Atg4a', 'Pcbp3', 'Gm48715', 'Prkab2', 'Casp1', 'Smyd1', 'Cnnm4', 'Fut8', 'Tmem56', 'Map6', 'Ctif', 'Rnf165', 'Slc5a3', 'Rhobtb2', 'Use1', 'Prxl2b', 'Eif3k', 'Tgoln1', 'Ogdh', 'Peg13', 'Dnajc27', 'BC029722', 'Pfdn6', 'Tjp1', 'Reep5', 'Ube2e2', 'Ap3s1', 'Gorasp2', 'Txnrd1', 'Mapt', 'Ucn3', 'Cyp19a1', 'Ogdhl', 'Nbdy', 'Supt16', 'Gm28884', 'Hsf2', 'Kdelr2', 'Pnck', 'Cd99l2', 'Plp1', 'Casr', 'Metap1d', 'Gm38604', 'Arhgdia', 'Cdkl2', 'Arntl2', 'Prdm13', 'Stat3', 'Nfkbia', 'Gm32014', 'Bmp1', 'Gm1992', 'Gucy2f', 'Gm37640', 'Rbpms', 'Card10', 'Lpcat2', 'Sptlc3', 'BC039966', 'Rbks', 'Cdkl3', 'Purg', 'Esrrb', 'Gm13912', 'Mpp4', 'Babam2', 'Rab11fip5', 'Pnpo', 'Ccdc153', 'Spink10', 'Adgb', 'Zfp995', 'Gpr165', 'Trpc1', 'Gpsm3', 'Gart', 'Mertk', 'Cbs', 'Ppp2ca', 'Bcorl1', 'Triqk', 'Ttpa', 'Clca3a1', 'Cfap70', 'Aff1', 'Nid2', 'Wnk4', 'Anxa6', 'Wsb2', 'Syngr1', 'Ctnnal1', '2810049E08Rik', 'Slc16a11', '1110017D15Rik', 'Mesd', 'Txndc5', 'Nenf', 'Otub1', 'Rhbdd2', 'Tmem151a', 'Hsph1', 'Iscu', 'Sdcbp', 'Zrsr2', 'Rtl5', 'Blcap', 'Tro', 'Mbnl3', 'C030014I23Rik', 'Rab9b', 'Mboat7', 'Gpr179', 'Fam183b', 'Drc1', 'Zhx2', 'Tub', 'Cfap46', 'Gkap1', 'Spg21', 'A530046M15Rik', 'Adcy6', 'Lmntd1', 'Pax5', 'Apoc3', 'Frat2', 'Baz2b', 'Gch1', 'Hivep3', 'Rnasel', 'Nbeal1', 'Nab2', 'Skor1', 'Iah1', 'Tmem181a', 'Matk', 'Tmem250-ps', 'Nkain1', 'Iqck', 'Jak1', 'Nkx2-4', 'Tnxb', 'Adprhl1', 'Lrriq1', 'Dnah10', 'Il4ra', 'Cd1d1', 'Slc14a1', 'G6pdx', 'Taf7l', 'Gm33680', 'Glra4', 'Gm36388', 'Gm39244', 'Eif2ak4', 'Ssc5d', 'Mccc2', 'Nup62cl', 'Sec11c', 'Whamm', 'Stk40', 'Zfp426', 'Stimate', 'Kcnk12', 'Nr1d2', 'Gm10710', 'Atp2c2', 'Gm34455', 'Gm30504', 'Lekr1', 'Gm19689', 'Rin3', '2310014F06Rik', 'Nxpe3', 'Mfsd2a', 'Rnaset2b', 'Gfpt2', 'Tet3', 'Fggy', 'Plvap', 'Gls2', 'Sertad2', 'Dna2', 'Radx', 'Gm41804', 'Lrrc23', 'F5', 'Kdm5d', 'Mia', 'Ttc39c', 'Gm10134', 'Lrrc6', 'Rdh10', 'Gm35721', 'Gm12367', 'Foxn2', 'Catsperg1', 'Car11', 'Pex11a', 'Ulk4', 'Rab36', 'Usp46', 'Nphp1', 'Dixdc1', 'Mid1ip1', 'Areg', 'Tmem179', 'Smap2', 'Zfp239', 'Erc1', 'Dtd1', 'Inafm1', 'Aktip', 'Sgsm1', 'Cetn2', 'Ksr2', 'Cmip', 'Fezf1', 'Spint1', 'Runx1', 'Krt17', 'Scn11a', 'St8sia3os', 'Hydin', 'Gsc', 'E130008D07Rik', 'Rhbdl1', 'D1Ertd622e', 'A730018C14Rik', 'Gm46329', 'Gm10000', 'Slc4a11', 'Samd9l', 'Optn', 'Omg', '2410124H12Rik', 'Trim8', 'Ing1', 'Trpa1', 'Cisd3', '4930523C07Rik', 'Apobec4', 'Efhb', 'Kif9', 'Lmcd1', 'Gm13589', 'Fam167a', 'Gm49016', 'Fgf8', 'Pi16', 'Kank1', 'Col4a5', 'Pax8', 'Gm14342', 'Morc4', 'Naf1', 'Gab1', 'Gm46515', 'Stat4', 'Gm35438', 'Adam34', 'Slc25a48', 'Gm42397', 'Dnah12', '1700012D14Rik', 'Gm9856', 'Il1rl2', '4930419G24Rik', 'Vmn1r200', '2410018L13Rik', 'Cmya5', 'Elmo2', 'Ccdc42', 'Gm29296', 'Dffb', 'Lamc1', 'Med12l', '1500035N22Rik', 'Elf4', 'Dmrta2', 'Pnma3', 'Ccdc82', 'Opn5', 'Gldc', 'Dynlrb2', '2310009B15Rik', 'Abca4', '2900041M22Rik', 'Nmu', 'C630031E19Rik', 'Slc16a14', 'Nek11', 'Jpt2', 'Arhgef33', 'Nostrin', '2900005J15Rik', 'Dnajc12', 'Ralgapa2', 'Mmgt2', 'Gm21847', '7630403G23Rik', 'Meig1', 'Uprt', 'Fut10', 'Muc3a', 'Gm31087', 'Slc38a11', 'Ikzf1', 'Gm4208', '1700003F12Rik', 'Fbxl12os', 'Pdpn', 'D630024D03Rik', '4932441J04Rik', '2610001J05Rik', 'Fibp', 'Gm31938', 'Rom1', 'Gm30613', 'Agtrap', 'Parp9', 'Slc40a1', 'Gm14004', 'Primpol', 'Tex16', 'Cyp4f17', 'Gm4890', 'Tmc5', 'Gm26973', 'T2', 'Cep83', '4930578M01Rik', 'P2rx4', 'Insm2', 'Junos', 'Mfng', 'A730036I17Rik', 'Gm31819', 'Spag4', 'E330013P04Rik', 'Gm20125', 'Sp110', 'Olfr25', 'Samd11', 'Parp4', 'Ak9', 'Rad51b', 'Arpc1b', 'Btbd16', 'Ces1d', 'Ccdc81', 'H2-M3', 'Gm38590', 'A730060N03Rik', 'Itgae', 'Ccdc172', 'Wee1', 'A830092H15Rik', 'Mgmt', 'Zfp800', 'Acss3', 'Dnah1', 'Alms1', 'Nme5', 'Prdx6', '6720489N17Rik', 'Acsl5', 'Npc2', 'Gm17399', 'Itga3', 'Gatad2a', 'Clec2l', 'Catspere2', 'Nap1l3', 'Zfas1', 'Micos13', 'Agap3', 'Afdn', 'Nagk', 'Cnga3', 'Cmas', 'Cct5', '2700054A10Rik', 'Mttp', 'Coq8b', 'Dmtn', 'Srsf7', 'Ncoa7', 'Pax2', 'Bub3', 'Lrrc8d', 'Hmx2', 'Pcolce2', 'Bri3bp', 'Ccdc39', 'Ggta1', 'Islr', 'Slc1a6', '1700012B09Rik', 'Tdp1', 'Casd1', 'Unc13a', 'Tpk1', 'Arsb', 'Jade1', 'Haus4', 'Gsx1', 'Ccdc184', 'Vegfb', 'Tango2', 'Hmx3', 'Gm14858', 'Mok', 'Tert', 'Metrn', 'Cpa4', '1700042O10Rik', '2410004I01Rik', 'Gm13963', 'Dpy19l2', 'Them7', 'Gm13446', 'Crtap', 'Gm7854', 'Gm10248', 'Fbxw21', 'Gucy2c', 'Slc7a2', 'Galnt15', 'Tekt2', 'Fancc', 'Pfkp', 'Fuom', 'Slc44a1', 'Wwox', 'Ier3ip1', 'Cep170b', 'Map9', 'Chchd4', 'Arhgap32', 'Pds5b', 'Nck2', 'Immp2l', 'Polr2g', 'Kcnq1ot1', 'Pygb', 'Shd', 'Tctex1d1', 'Usp13', 'Efcab2', 'Rtl1', 'Cd40', 'Bckdhb', 'Lrp8os3', 'a', 'Gm12153', 'Tspan4', 'Cdk5rap2', 'Cacna1d', 'Alg2', 'Hmgn3', 'Ado', 'Gm48779', 'Krt90', '6030498E09Rik', 'En1', 'Acta1', 'Col6a6', 'Wdr72', 'Kcnj11', 'Gm5441', '1700017N19Rik', 'Olig2', 'Gm28055', 'Gm30524', 'Asna1', 'Slc6a8', 'Gad1os', 'Phactr3', 'Rtn2', 'Ranbp6', 'Sil1', 'Gm4881', 'Panx2', 'Zfp622', 'Eml2', 'Plekhb2', 'B230217C12Rik', 'Nap1l2', 'Crebl2', 'Polr2j', 'Idh3b', 'Gdap1', 'Snap91', 'H1fx', 'Coa6', 'Fam241b', 'Gm31356', 'Tbx19', 'Hlcs', 'Foxd2', 'Hsdl2', 'Hsd17b11', 'Stk39', 'Tsn', 'Gm35733', 'Fbln7', 'G930045G22Rik', 'Igsf5', 'Rasef', 'Idnk', 'Arhgap27os2', 'Pi15', 'Abcc9', 'Pmch', 'Ubl3', 'Unc13d', 'Hoga1', 'Fgf2', 'Etfbkmt', 'Rgs22', 'Omp', 'Nkx2-2os', 'Ssbp3', 'Rdx', 'Tbc1d22a', 'B230118H07Rik', 'Pcbp1', 'Mrpl34', 'Txn1', 'Snhg8', 'Rpgrip1', 'Nanos1', 'Ppp2r5d', 'Slc26a11', 'Sox14', 'Otp', 'Agrp', 'Gm47757', 'Hmga1', 'Gm19412', 'Atp7a', 'Col4a4', 'Il13ra1', 'Hddc2', 'Dera', 'Gucy1a2', 'Prkra', 'Sfmbt1', 'Pdgfrb', 'Mfsd6', 'Col4a3', 'Actn1', 'Tsga10', 'Gm40477', 'Gm16701', 'Gm26911', 'Idh1', 'Mroh5', 'Trim14', 'Gm26777', 'Atp2c1', 'Gm35842', 'Kiss1', 'Ltbp2', '2900060N12Rik', 'Plekha5', 'Dnah8', 'Gm10432', 'Vim', 'Il15ra', 'Pkhd1l1', 'Ppargc1b', 'Pdcd7', 'Txndc17', 'Atp2b3', 'Pgrmc1', 'Chchd7', 'Pianp', 'Zfp335os', 'Haghl', 'Ptprb', 'Tbx3os1', 'Qrfp', 'Hcrt', 'Clcn5', 'Skor2', 'Pomc', 'Gm20757', 'Fuca1', 'Vgll2', '4933406B17Rik', 'Phldb1', 'Gas2', 'Trim62', 'Stk19', 'Ros1', 'Gm11508', 'Smim20', 'Stip1', 'Phf1', 'Tlk1', 'Zmat1', 'Rfx2', 'Gm16499', 'Wdpcp', 'Shisal2a', 'Gm30363', 'Sqle', 'Trac', 'Gstp1', 'Tbx3os2', 'Kansl1l', 'Gm9947', 'Usp51', 'Hist1h2ac', 'Bdkrb2', 'Tmco4', 'Leprot', 'Ptger4', 'Mxi1', 'Npvf', 'Prlh', 'Polg2', 'Sc5d', 'Slc12a2', 'C030018K13Rik', 'Slc16a9', 'Mrln', 'Bard1', 'Gm49171', 'Apod', 'Rab30', 'Sft2d2', 'Chpt1', 'Col6a4', 'Mta3', 'Tcea3', 'Gm26713', 'Jph2', 'Uaca', 'Gm45911', 'Prokr1', 'Sox21', 'Tram2', 'Acot11', 'Htr3b', 'Kntc1', 'Aoah', 'Tnfsf11', 'Abhd2', 'Jund', 'Atxn7l1', 'Cyb5r3', 'Tfcp2l1', 'Mark1', 'Ttbk2', 'Nell1os', 'Lgalsl', 'Il31ra', 'Nr5a1', 'Parpbp', 'Tfap2a', 'Gm10863', 'Setdb2', 'Stx3', 'Gm13483', 'Gm43122', 'A930003A15Rik', 'Dmrtb1', 'Galnt2', 'Nuak2', 'Sel1l2', 'Gm36903', 'Rhpn1', 'Gm43672', 'Atf7ip2', 'Phf11c', 'Trim68', 'Lactb2', 'Galnt12', 'Iigp1', 'Plcz1', 'Oca2', 'Gm26688', 'Lrat', 'Capn2', 'Gm16152', 'Pard6a', 'Pidd1', 'Gm10475', 'Pon2', 'Gm48749', 'Kctd15', 'Ces5a', 'Mturn', 'Gclm', 'Rbm19', 'Gm13264', 'Ggt5', 'Nr5a1os', 'Ccdc157', 'Nim1k', 'Nup107', 'Reck', 'Gpd2', 'Gtdc1', 'Atp1b3', 'Pdxk', '0610010K14Rik', 'B3gat3', 'Rtraf', 'Chmp2b', 'Ufm1', 'Mup6', 'Vsx2', 'Barhl1', 'Gm27246', 'Sim2', 'Clgn', 'Il6st', 'Rbbp8', 'Optc', 'En2', 'Gm29536', 'Cdh1', 'Cldn11', 'BC051142', 'B930018H19Rik', 'Gja1', 'Abcb4', 'Gucy1b2', 'Plat', 'Afmid', 'BC049352', 'Gm12144', '2610042L04Rik', 'Dnajc28', 'Gm49575', 'Gm40437', 'Tnfsf8', 'Cerkl', 'Cfap47', 'Zfp341', 'Oas3', 'Gstm2', 'Armh1', 'Gm43948', 'Neurog2', 'Gm38811', 'Saa1', 'Slc6a13', '4922502N22Rik', 'Gm33586', 'Gm15482', 'Tyms', 'Gm49267', 'Olfr1259', 'Slc26a7', 'Gca', 'Garem2', 'Cnmd', 'Gm33906', '2600006K01Rik', 'Evpl', 'Neo1', 'Stt3b', 'Rfc1', 'Gm30624', 'Ccdc92', 'Dcaf12l1', 'Gm27239', 'Tcf24', 'C1ql4', 'Lmx1a', 'Lmx1b', 'Oxt', 'Caprin2', 'Foxa1', 'Gm50423', 'Rufy4', '1110038B12Rik', 'Tmed3', 'Gm49732', 'Mageh1', 'C130021I20Rik', 'Mindy2', 'Exoc7', 'Irx3', 'AI854703', 'Smyd4', 'Irx5', 'Gm43824', 'Fshr', 'Mymk', 'C430049B03Rik', 'Efhc2', 'Gm1715', 'Svep1', 'Ms4a7', 'Scml2', 'Npw', 'Gpr162', 'Magt1', 'Gsta4', 'F3', 'Aen', 'Zfp791', 'Klhdc4', 'Ccdc15', 'Gm15892', 'Ankrd50', '4921518K17Rik', '6530402F18Rik', 'Gm4221', 'Sigmar1', '4930570B17Rik', 'Churc1', 'Rnaseh2b', 'Dglucy', 'Mrps26', '2410006H16Rik', 'Hspa5', 'Klf4', 'Tfap2b', 'Rbm47', 'Pou4f2', '9030622O22Rik', 'Gm45587', 'Irx4', 'Mipol1', 'Tlx3', 'Gm12116', 'Tlx1', '0610043K17Rik', 'Slc6a2', 'Irx6', 'Lbx1', 'F2rl2', 'Spidr', 'Dsg1a', 'Kremen2', 'Grk4', 'Rtbdn', 'Gm5086', 'Ube2u', 'Parp12', 'Gm34004', 'Dmrta2os', 'Gngt2', 'Sgms2', 'Abhd15', '4930500L23Rik', 'Gm11732', 'Cndp1', 'Foxa2', 'Krt18', 'A530065N20Rik', 'Gm19461', 'Cyp4x1', 'BC067074', 'Scel', 'Izumo4', 'Efcab11', 'Mrc2', 'Gm47515', 'Otogl', 'Cenpe', 'Gm15688', 'Gm16267', 'Parp14', 'Npb', 'Plscr1', 'Sparc', 'Wdsub1', 'Insc', 'B230312C02Rik', 'Jhy', 'Tmem94', 'Syne4', 'Xdh', 'Depdc1b', 'Rapsn', 'B9d2', 'Gm12576', 'Gm43950', 'Gm7967', 'Slc37a1', 'Cnpy1', 'Gm14207', 'Gm43112', 'Gm26708', 'Ppef1', 'Gm26862', 'Gm48094', 'Lncbate1', '4933427D06Rik', 'Mroh1', 'Igsf9', 'Wars', 'Rprd1a', 'Smn1', 'Nsfl1c', 'Tstd1', 'Bcas1', 'Ndufs8', 'Gm49087', 'Fev', 'Slc6a4', 'Gata3', 'Pax7', 'Nkx6-1', 'Gata2', 'Flot2', 'Aida', '4933429O19Rik', 'Ctsl', 'Tecrl', 'Flt4', 'Wfdc12', 'Cryba2', 'E2f7', 'Nkx6-2', '4930527B05Rik', 'Lhx4', 'Gm31121', 'Slc35b3', 'Csf2rb2', 'P4ha2', 'Gm15397', 'Hotairm1', 'Unc45b', 'Tnfrsf11b', 'Gm16701', 'Panct2', 'Asb16', 'Rsph9', 'Nlrx1', 'Celrr', 'Gm44992', 'Olfr920', 'Lrrk1', 'Hoxb3', 'Chrm5', 'Cpsf4l', 'Spag5', 'Unc45bos', 'Gm15418', 'Ltbp4', 'Cox7a1', 'Ttf2', 'Gm12648', 'Scube3', 'Prep', 'Gm26901', 'Exoc1', 'Krt26', 'Csf2rb', 'Nat8f3', 'Flvcr2', 'Crct1', 'Tinag', 'Wdfy4', 'Oas1e', 'Gm5868', 'Macc1', 'Enpep', 'Sapcd1', 'Gm38642', 'Tph1', 'A2m', 'Lonrf3', 'Gpr35', 'Gm26902', 'Ifi35', 'Gm49729', 'Col28a1', 'Gm13849', 'Stom', 'Crip1', 'Il4', '4930545L08Rik', 'Myo15', 'Cpt1a', 'Hspa12b', 'Galnt5', 'Tspo2', 'Pxmp2', 'Pole', 'Clec1a', 'Adamts10', 'Lrrc8a', 'Kctd9', 'Raly', 'Ehd3', 'Zbtb38', 'Zwint', 'Nsd2', 'Atp6v1c1', 'Acss2', 'Psmb10', 'Nwd1', 'Asl', 'Myo1a', 'Pitx1', 'Evx2', 'Pou4f3', 'Tmem29', 'Evx1os', 'Gm47071', 'Bhlhe23', 'E230029C05Rik', 'Gm36560', 'Evx1', '5430401H09Rik', 'Gm40383', 'Bfsp2', 'Iqcf3', 'Gm45187', 'Gm13497', '9130008F23Rik', 'Ccdc36', 'AI467606', 'Six2', 'Gm15594', 'Syk', 'Fmnl3', 'Pitx3', 'Asap3', 'Gm2762', 'A730049H05Rik', 'Dnah2', 'Gm43614', '4930520O04Rik', 'Sfxn5', 'Ak8', 'Slc10a7', 'Rbp3', 'Gm14344', 'Rdm1', 'Pecam1', 'Gm20631', 'Serping1', 'Gm45092', 'Gpr141', 'Spa17', 'Espn', 'Slc27a2', 'Mlf1', 'Morc1', 'AC109619.1', 'Gtf2f2', 'Stat1', 'Gm48535', 'Ppif', 'Trpm2', 'Hepacam2', 'Hoxb3os', 'Slc38a4', 'Gm37459', 'Art4', 'Gm32122', 'A330076C08Rik', 'Gm26861', '2610027F03Rik', 'Gm32005', 'Aqp6', 'Gm12426', 'Gm45490', 'Nckap1l', 'Lrrc75a', 'Best3', '0610040F04Rik', 'Pdk3', 'Gm12023', 'Mgl2', '1700125H20Rik', 'Lin7b', 'Gm26608', 'Rab39', 'Dmrtc1a', 'Hsd17b2', '1700048O20Rik', 'Gipr', 'Crot', 'Lrrc3', 'Gpr37', 'Cox4i2', 'Cmah', 'Deup1', 'Pou2f3', 'Gm13791', 'Ero1lb', 'Gm12963', 'Kif19a', 'Gm10827', 'Trim67', 'Begain', 'Lpcat4', 'Disp1', 'Ppp4r1', 'Gosr1', 'Pth2', 'Cradd', 'Zmym1', 'Fgf7', 'Slfn8', 'Ubap1l', 'A330049N07Rik', 'Scara5', 'Gm12132', 'Kras', '6030443J06Rik', 'Rubie', 'Errfi1', 'Galk2', 'Poln', 'Fer', 'Gm27224', 'Mpg', 'Smim18', 'Pla2g6', 'Itgb5', 'Gm15934', 'Pdzd7', 'Gm42829', 'Zswim7', 'Gm29328', 'Ehd4', 'Atic', 'Gm31793', 'Lin9', '4930412C18Rik', 'Rsrc1', 'Mapk9', 'Ndufa10', 'Tmem201', 'Usp53', 'Ccdc93', 'Pmpca', 'Mettl15', 'Litaf', 'Stpg2', 'Arg1', 'Trim21', 'Gm1968', 'Slc12a3', 'Plscr5', 'Il15', 'Gm19585', 'Rhpn2', 'Trub1', '6030407O03Rik', 'Fcmr', 'Ncapg2', 'Ephx1', 'Ttc12', 'Fam161a', 'Gm36642', 'Timp4', 'Lhfpl5', 'Gsr', 'Cenpw', 'Mapk12', 'Pygl', 'Rtp4', 'Lrrc17', 'Cbr3', 'Tdrd12', 'Wfdc10', '9030404E10Rik', 'Esyt1', 'Col9a2', '6330576A10Rik', 'Tm4sf5', 'Epp13', 'Capn1', 'Lgals7', 'Mafk', 'Krtap17-1', 'Gm48727', 'E130006D01Rik', 'Rassf6', 'Klhl25', 'Ifi213', 'Olfr273', 'Trp53bp2', 'Cluh', 'Ptch2', 'Pdk2', 'Pkhd1', 'Ttc29', 'Myl2', 'Slc15a5', 'Sult3a2', '4930486I03Rik', 'Gm11844', 'Il18', 'A230004M16Rik', '4930543I03Rik', '1700027H10Rik', 'Clec5a', 'Dyrk4', 'Gm26802', 'Milr1', 'Gm49685', '2900052N01Rik', 'Xk', 'Tdrd5', 'Gbp6', 'Hjurp', 'Agl', 'Gm30054', 'Trarg1', 'Ccdc174', 'Smad9', 'Tmem229b', 'AU023762', 'Ky', 'A930017K11Rik', 'Platr25', 'Gdpd4', 'Cyp2j6', 'Akr1b3', 'Arrb2', 'Ptx3', '4930444A19Rik', 'Hspg2', 'Slc27a3', 'Hepacam', 'Gm13522', 'Gm31282', 'Slc6a5', 'Pax3', 'Ints7', 'Fbxo27', 'Tradd', 'Fam131c', 'Gm14246', 'Ahcy', 'Dkk1', 'Gm42705', 'Mgarp', 'Tnfrsf1b', 'Prrt4', 'Hist1h2be', 'Acsl6', 'Zhx1', 'Gm16105', 'Prdm6', 'Gm16984', 'Spats2', 'Nps', 'Gm36325', 'Col9a1', 'Trpm4', 'Rgs13', 'Dpf1', 'Aif1l', '1700113H08Rik', 'Il23r', 'Tom1', 'Gm13404', 'Olfr1033', 'Panx3', 'Lum', 'Ccn5', 'Gm10637', '2010013B24Rik', 'Ifih1', 'Adora2b', 'Nrg4', 'Slc27a6', 'C030047K22Rik', 'Col4a6', 'Pter', 'Gm5095', '4930578E11Rik', 'Lmbrd2', 'Ap3d1', 'Mrps12', 'Raf1', 'Smarca4', 'Rnf38', 'Radil', 'Prkci', 'Slc41a2', 'Slc39a9', 'Tafa3', 'Vwa1', 'Tnfrsf13c', 'Pla2g2f', 'Lgals9', 'Stab2', 'Anxa3', 'Hs3st6', 'C030005K06Rik', 'AA387883', '4930500H12Rik', 'Hspb11', 'Gpr27', 'Gm15738', 'Gm2990', 'Mad2l2', 'Phox2b', 'Mecom', 'Arid3b', 'Tal1', 'Hoxc4', 'Lhx3', 'Hoxb5', 'Foxd3', 'Gm12688', 'Hoxd3', 'Gm11884', 'Cr2', 'Prdx4', 'Hoxb4', 'Hoxb2', 'Bmp2k', 'Hoxa4', 'Gm28516', 'Ccnb1ip1', 'Disc1', 'Btla', 'Fam83b', 'Lnp1', 'Spata33', 'Smtnl2', 'Prrg4', 'Fgfr4', '4933426B08Rik', 'A730006G06Rik', 'Ecscr', 'Nkain4', 'Rnf113a1', 'Panx1', 'Hoxa5', 'Gm42696', 'Lpar4', 'Lrtm1', 'Gm15631', 'Abcc3', 'Gm4107', 'Gm20647', 'Tbc1d8', 'Foxd4', 'Gm15414', 'Gm6994', 'Gm47520', 'Gm16499', 'Oat', 'Spry1', 'Plcd3', 'Tex50', 'Fam204a', 'Tbrg1', 'Txnrd3', 'Gm4681', 'Gm12022', 'Fry', 'Syf2', 'Slc41a3', 'Trmt12', 'Pqbp1', 'Irak3', 'Prdm16os', 'Cmc2', 'Zranb3', 'Lhpp', 'Hoxaas3', 'Hoxd4', 'Tsfm', '4930469K13Rik', 'Dbh', 'Phox2a', 'Melk', 'Ndufv1', 'Emc9', 'Ublcp1', 'Ckmt1', 'Fn3k', 'Acyp1', 'Cuta', 'Atoh1', 'Caly', 'Bnip3', 'Yif1b', 'Tmem147', 'Vps28', 'Smim12', 'Psmb5', 'Flii', 'Hoxa3', 'Psmc4', 'Endog', 'Ubl7', 'Sco2', 'Cstb', 'Ppa2', 'Tmem184c', 'Asns', 'Gm11454', 'Grhpr', 'Timm50', 'Taldo1', 'Alkbh7', 'C1qbp', 'Fbll1', 'Clec10a', 'ETV3L', 'Mgam', 'Mrpl32', 'Copb2', 'Pcna', 'Tpgs1', 'Tmem160', 'Rab4b', 'Ndufa9', 'Ppa1', 'Comtd1', 'Cope', 'Ckap4', 'Ndufs3', 'Med31', 'Znrd2', 'Pdcd6', 'March5', 'Mrpl15', 'Hadhb', 'Adh5', 'Gm50330', 'Scamp3', 'Psmb3', 'Mag', 'Ctsf', 'Esd', 'Cdhr3', 'Alkbh6', 'Unc50', 'Etfb', 'Zmat5', 'Fahd1', 'Gstm5', 'Mcee', 'Gtf2b', 'Ppp1r35', '4732471J01Rik', 'Mrps31', 'Coq7', 'Mrpl22', 'Hist3h2ba', 'Fh1', 'Lsm4', 'Cbr1', 'Phpt1', 'Lgmn', 'Tmem14c', 'Mrpl46', 'Slc35g2', 'Ssr2', 'Mrps22', 'Mrpl2', 'Ahsa1', 'Cyth2', 'Nfkbib', 'Flot1', 'Ptcd2', 'Psmb6', 'Mcts2', 'D230022J07Rik', 'Dock2', 'Tgfb1', 'Cfap299', 'Ctcflos', 'A230108P19Rik', 'Aldh1a7', 'Atp13a4', 'Abhd14a', 'Gmnc', 'Nccrp1', '6820408C15Rik', 'Fndc10', '8030451A03Rik', 'Mgam2-ps', 'Tcea2', 'Tmem185b', 'Slc13a1', 'Fblim1', 'Vmn1r196', 'Vmn1r207-ps', 'Gm47591', '1700021F05Rik', 'Ankrd9', 'Sf3a2', 'Naa38', 'Idh3g', 'Med29', 'Dapk3', 'Lin37', 'Urod', 'Nol3', 'Psmg1', 'Nt5c', 'Apex1', 'Bloc1s1', 'Ethe1', 'Aimp2', 'Pelo', 'Mzt2', 'Spin2c', 'Mrpl16', 'Ankrd1', '6330418K02Rik', 'Hint2', 'Tmem258', 'Slc25a33', 'Emc4', 'Uqcrc1', 'Polr2e', 'Gadd45gip1', 'Tm2d3', 'Mrpl23', 'Prdx1', 'Trappc5', 'Tex264', 'Mrpl49', 'Wdr83os', 'Mrps11', 'Yars2', 'Fahd2a', 'Pold2', 'Tmem53', 'Mterf2', 'Mrpl28', 'Timm10', 'Psma5', 'Tm2d2', 'Gm10941', 'Bola1', 'Exosc4', 'Osgep', 'Tmbim4', 'Tubg1', 'Tmem218', 'Psmc2', 'Ebpl', 'Wdr74', 'Mrpl4', 'Dnajc4', 'Cmc1', 'Csnk2b', 'Rnaseh2c', 'Rnh1', 'Phb', 'Acot13', 'Ndufb6', 'Dad1', 'Med30', 'Mrps25', 'Tpd52l2', 'Akr7a5', 'Sdhb', 'Ruvbl1', 'Adrm1', 'Mrpl55', 'Akr1b10', 'Eif1ad', 'Mdh2', 'Mdh1', 'Cox5a', 'Pkm', 'Fkbp2', 'Pgam1', 'H2afx', 'Yipf3', 'Commd1', 'Polr2f', 'Eif3g', 'Pop7', 'Arl6', 'Pdzd11', 'Zcchc18', 'Tspyl4', 'Snap47', 'Slc25a4', 'Ttc3', 'Ndufb8', 'Mea1', 'Gm20300', 'Gm12462', 'Xlr3b', '4930563E22Rik', 'Nudt22', 'Psma6', 'Eid2', 'Cfap298', 'Lonp1', 'Spr', 'Mtx1', 'Nat9', 'Apbb3', 'Atg101', 'Polr2l', 'Fkbpl', 'Dmac1', 'Nudt9', 'Pus1', 'Nprl2', 'Gpn3', 'Ech1', 'Nudt14', 'Creb3', 'Arxes1', 'Rpp25l', 'Hspbp1', 'Timm17b', 'Mettl26', 'Klhl11', '2310009A05Rik', 'Mrps30', 'Aasdhppt', 'Tsr3', 'Tmub1', 'Isyna1', 'Cdk4', 'Eif6', 'Prr7', 'Hoxc5', 'Usp27x', 'Hoxb8', 'Hoxb6', 'Gcg', 'Npff', 'Prok1', 'Pyy', 'Nkx6-3', 'Dmbx1', 'Hoxb7', 'Afp', 'BC034090', '6530409C15Rik', 'Hoxc6', 'Cyp4v3', 'Gm45352', 'Tex13c2', 'Trim7', 'Wnt11', 'Slc35f2', 'Sec1', 'A230103O09Rik', 'Wfdc1', 'Msmo1', '1700028P14Rik', 'Olfr78', 'Ppara', '4930432L08Rik', 'Gm36736', 'Star', 'Gm27241', 'Serpinb7', 'Caskin1', 'Fbxo3', 'Usp11', 'AW554918', 'Dcun1d4', 'Hoxa7', 'Dynap', 'Kifc2', 'Zpbp', '9430038I01Rik', 'Gstt1', 'Ehf', 'C77080', 'Caps2', 'Amer1', 'Nosip', 'Pwwp3a', 'Crlf3', 'Cfap69', 'Sfxn3', 'Slc28a2', 'CJ186046Rik', 'Lzts2', 'Ankdd1a', 'Pwp1', 'Gyg', 'E2f3', 'Yipf2', '2310026I22Rik', 'Apoa1', 'St3gal3', 'Nhlh1', 'Glipr2', 'Gm12158', 'Gm7706', 'Gucy2d', 'Gm27188', 'Atg9b', 'Abca2', 'Smim13', 'Nfic', 'Sh3bgrl3', 'Tprgl', 'Znhit1', 'Gm12408', 'Vmn2r84', 'Abca7', 'Fam98a', 'Emc6', 'Kars', 'Gimap6', 'Agmo', 'Cdk5rap3', 'Olig1', 'Stac3', 'Mknk1', 'Rpusd1', 'Gm31752', 'Syt3', 'Asb2', 'Ccdc85c', 'Mab21l3', '4932438H23Rik', 'Cenps', '9330198N18Rik', '2900045O20Rik', 'B830017H08Rik', 'Mcam', 'P2ry12', 'Padi1', 'Gm36356', 'Slc44a3', 'Tslp', 'Morc2b', 'Sugct', 'H2-Ab1', 'Speer4cos', 'Tyrp1', 'Tdrp', 'Kank2', 'Dazap2', 'Gm16141', 'Hoxb5os', 'Rln3', '2810404M03Rik', 'Xirp2', 'Gm29266', 'Fat2', 'Tmprss2', 'Gm26756', 'Pphln1', 'Cptp', 'Ptgr2', 'Lrig3', 'Gm41192', 'Suv39h1', 'Pcdhb17', 'Pard6b', '1700024B18Rik', 'Tbx18', 'Adat1', 'Fads1', 'Lcp2', 'Gm45639', 'Gabrr1', 'Ceacam10', 'Il27ra', 'Svs5', 'Alpk1', 'Gm4675', 'Tpgs2', 'Lss', 'Smim11', 'Ccdc66', 'Fdx1', 'Dchs1', 'Nfe2l3', 'Prorsd1', 'Racgap1', 'Gpr137', 'Fads6', 'Mtx3', 'Tufm', 'Slc4a9', 'Hebp2', 'Rimkla', 'Pno1', 'Degs1', 'Ak1', 'Arid3c', 'Btc', 'Mfsd5', 'Qrsl1', 'Gbp7', 'Vsig8', 'Tcn2', 'Rpa1', 'Gm16294', 'S1pr1', '4930511M06Rik', '4930590J08Rik', 'Gm17767', 'Il12rb2', 'Kyat3', 'Cd74', '9330111N05Rik', 'Upp1', 'Hhatl', 'Eme2', 'Sphk1', 'Gm32816', 'Sfn', 'Fam78a', 'Exosc5', 'Apol8', 'Gm35501', 'Tor3a', 'Gm13530', 'A230087F16Rik', 'Gm26936', 'Gm16758', 'Prdm9', 'Mpi', 'Pdzk1ip1', 'Kcnd1', 'Gm30085', 'Tek', '4921504A21Rik', 'Slc35c2', 'Stxbp3', 'Capn6', 'Gfm1', 'Map1a', 'Pgk1', 'Dgkq', 'Gm15494', 'Pank4', 'Alas1', 'Gm32884', 'Abca13', 'Bmp8a', 'Gsc2', 'Paqr4', 'Dsg3', 'Gmppa', 'Abcc2', 'Bag6', 'B230307C23Rik', 'Gm45740', 'Ruvbl2', '9130019P16Rik', 'Wdr54', 'Acadvl', 'Dpp7', 'Fastkd3', 'A230001M10Rik', 'Abcb9', 'Gm41333', 'H2-Q1', 'Gm14133', 'Slc9a3', 'Erich2', 'Gm29502', 'Gfap', 'Tmem202', 'Tbxas1', 'Dtnbp1', '2300009A05Rik', 'Rcan1', 'Snapc5', 'Mrps18c', 'Ubxn1', 'Banf1', 'Dr1', 'Yeats4', 'Eif4a3', '4930455G09Rik', 'Zfp874a', 'Ace', 'Abcb5', 'Mrpl35', 'Gm34397', 'Pik3cb', 'Mapk8', 'Ddit3', 'Cpeb2', 'Mboat2', 'Adgrl4', 'Aldh5a1', 'Card19', 'Zfp760', 'Prtn3', 'Gm35256', 'Gm49741', 'Cd59b', 'Cox7b2', 'Pdgfrl', 'Tcaf2', '2810429I04Rik', 'Nqo2', 'Ilrun', 'Rnf149', 'Bag2', 'Cers4', 'Spryd3', 'Zbtb7a', 'Rab28', 'Col1a2', 'Gabrr2', 'Epyc', 'Pkd2l1', 'Cps1', '2700046A07Rik', 'Zfp758', 'Rflna', '5730409E04Rik', 'Fsbp', 'Rad54b', 'Hook2', 'Sh2d4a', 'Nr6a1os', 'Lyrm7', 'Impa1', 'Gm36723', '2010007H06Rik', 'Gm9750', 'Eci1', 'Abcc12', 'Nr6a1', 'Dek', 'Snx10', 'Glb1l2', 'Spcs3', 'Sdhaf3', 'Msx1', 'Pcp2', 'Amhr2', '4430402I18Rik', '2610035D17Rik', 'Ctnnd1', 'Tnni3', 'Tgfb3', 'Mospd1', 'Mrpl39', 'Rabggta', 'Cdr1', 'Sp5', 'Rd3l', 'Acsbg1', 'Ccdc61', 'Tube1', 'Lrrc27', 'Nrk', '4930430F21Rik', '5730419F03Rik', 'Vmn2r87', 'Gm20275', 'Ankrd31', 'Wdr76', 'Gm26724', 'Trappc1', 'Hist3h2a', 'Arfgap1', 'Acadm', '1190005I06Rik', 'Paqr9', 'Gdf6', 'Crisp1', 'Tmem233', 'Gm11309', 'Gm37245', 'Myf5', 'Gm32926', 'Tmem246', 'Gpr183', 'Vmn1r208', 'Slc12a1', 'Pdk4', '9030624G23Rik', 'Apobec1', 'Gpr37l1', 'Pank1', 'Gm38593', 'Dram1', 'Evc', '2210011C24Rik', 'Cdkn1b', 'Gm15918', 'Zbtb42', 'Abca5', 'Chrdl2', 'Gm44096', 'Mrps6', 'Slc5a6', 'Frat1', 'Tmem204', 'Gm9899', 'Arhgef19', 'Mlxipl', 'Lta', 'Lingo4', 'Ighg3', 'Gsn', 'C1qtnf1', 'Morrbid', 'Ackr4', 'Nrl', 'Gm15083', 'Gm44626', 'Srrm4os', 'Smug1', 'Otop1', 'Gstt2', 'Gm31645', 'Gm15608', 'Zfp937', 'Ofcc1', 'Loxl2', 'Enpp3', 'Sfrp5', 'Clec14a', 'Defa24', '4930532I03Rik', 'Gnb3', 'Rwdd4a', 'Tbx20', 'Hsd11b2', 'Cox8b', 'Acsl1', 'Gm15469', 'Cyth3', 'Adgre1', 'Mettl27', 'Tmem207', 'Taf9b', 'Ranbp3l', 'Anxa1', 'Atp2a3', 'Ildr1', 'Tgm6', 'Gm42208', 'Mill2', 'Ush1c', 'Fbxo40', 'Mrc1', 'Mtap', 'Nat8f6', 'Pepd', 'Cdcp1', 'Gm36660', 'Zc3hav1', 'Gm15689', 'Vwce', 'AI661453', 'Sdc1', 'Npy4r', 'Gm20319', 'Gm31641', 'Wnt10b', 'Cldn2', 'Gm34821', 'Fgf20', 'Neurl3', 'Sstr5', 'P2rx2', 'Id1', 'Defb42', 'Olfml3', 'Fgl2', 'Rida', 'Nppb', 'Map7d3', 'Uts2b', 'Acer2', '3930402G23Rik', 'Ptger2', 'Gm13775', 'Gm17173', 'A4galt', 'Rec114', 'Tmc3', 'Dnah6', 'Vill', 'Gm32857', 'Hist1h2ap', 'Olfr574', '1700001C19Rik', '1500015L24Rik', 'Mylk4', 'Ikzf3', 'Kirrel2', 'Tdh', 'Slc22a21', 'Gm5', 'Gdf5', 'Card14', 'Mgat4a', 'Rufy3', 'Slc31a1', 'Afap1l2', 'Gpsm1', 'Ldlrap1', 'Dclk2', 'Gnrh1', 'Pkd1l2', 'Gabra6', 'Cbln3', 'Ly6d', 'Gm33948', 'Rasa2', 'Six1', 'Rrbp1', 'Gm42912', 'Epcam', 'Fam92b', 'A430106G13Rik', 'Nfkbie', '1700094D03Rik', 'BC051408', 'Lnx2', 'Atp11a', 'Plec', 'Gm27032', 'Ppp1cc', 'Als2', 'Asic5', 'Wwp1', 'Tmprss6', 'Ppp1r12b', '1810007D17Rik', 'Gm47359', 'C530044C16Rik', '1700087I21Rik', 'Gm34299', 'Tmc7', 'Nln', '4930581F22Rik', 'Phtf2', 'Zbtb10', 'Coq8a', 'Lox', 'Cpxm2', 'Gm12146', 'Gm14033', 'Noct', 'Rhcg', 'Lrp8os2', 'Msrb1', 'Tmem86a', 'Txnl4b', 'Cox15', 'Kctd10', 'Pold4', 'Kctd21', 'Gan', 'Ggact', 'Lurap1', 'Igf2r', 'Crtam', 'Bcl2l15', '2700038G22Rik', '6430571L13Rik', 'Ttyh2', 'Mybpc3', 'Rasl12', 'Fgfr1op', 'Klc3', 'Tmem50a', 'Gm15564', 'Rgl3', 'Asgr1', 'Cited4', 'Cfap57', 'Gm12198', 'Adgrb1', 'Gm45459', 'Rapgef1', 'Hadha', 'Fgd1', 'Gm10862', 'Tmem169', 'Nop56', 'Zfp318', 'Obscn', 'Bsnd', 'Nqo1', 'Vps13a', 'Ddhd1', 'Eml5', 'Rab6b', 'Hdac4', 'Slc9a3r2', 'Unc79', 'Rabgap1l', 'Fnbp1', 'Cyld', 'Mex3a', 'Pde6g', 'Gm44196', 'Tulp1', 'Tc2n', 'Fabp12', 'Gpr17', 'Sox10', 'Cspg4', 'Neu4', 'Cenpf', 'Lockd', 'Cdkn2c', 'Hmgb2', 'Mki67', 'Top2a', 'Prc1', 'Cks2', 'Ube2c', 'Rdh5', 'Frmpd2', 'Pclaf', 'Zcchc24', 'Gm29260', 'Lims2', 'S100a1', '9630013A20Rik', 'Enpp6', 'Cnp', 'Gjc3', 'Kif11', 'Tpx2', 'Nusap1', 'Aspm', 'Knl1', 'Smc4', 'Ect2', 'Ckap2', 'Ezh2', 'Hmmr', 'Ckap2l', 'Hmgn2', 'Trim59', 'Gltp', 'Sirt2', 'S100a13', 'Hist1h1b', 'Rrm2', 'Mms22l', 'Tmpo', 'Lmnb1', 'Uhrf1', 'Draxin', 'Trf', 'Mog', 'Tmem88b', 'Ppp1r14a', 'Notch1', 'Hells', 'Mcm6', 'Opalin', 'Aspa', 'Nasp', 'Apoe', 'Gm10561', 'Birc5', 'Ddah2', 'Cks1b', 'Cdca8', 'Tsc22d4', 'Adamts4', 'Crx', 'Atad2', 'Gmip', 'Ccna2', 'Mfap2', 'Hist1h1e', 'Erbb3', 'Gm42047', 'Cdk1', 'Rcor2', 'Gal3st1', 'Kcnj10', 'Hapln2', 'Unc119', 'Smad1', 'Qdpr', 'Serf1', 'Slf1', 'Rps27l', 'H2afv', 'Rftn2', 'Hat1', 'Zfp704', 'Jarid2', 'Mex3b', 'Pou2f1', 'Atf7', 'Jpt1', 'Gpc2', '1700047M11Rik', 'Emp2', 'Gm16168', 'Hes6', 'Meox2', 'Pde6c', 'Casp3', 'Atat1', 'Irs1', 'Gm36988', 'Tnni1', 'Cst3', 'Dbndd2', 'Ybx1', 'Tmem141', 'Lrba', 'Gm16351', 'Twsg1', 'H3f3a', 'Plxnb3', 'Dut', 'Ubald2', 'Anp32b', 'Gcgr', 'Vmn2r1', 'Nras', 'Gng11', 'Ninj2', 'Cdh19', 'Gramd3', 'Rnf122', 'Cldn14', 'Snhg5', 'Arhgap11a', 'Gm12802', 'Elp4', 'H2afj', 'Rpl22', 'Neurod4', 'C030029H02Rik', 'Bach1', 'Cd81', 'Sema4d', 'Ccdc88a', 'Bzw2', 'Epn2', 'Acaca', 'Tubb5', 'Lrp1', 'Odc1', 'Itm2b', 'Dctpp1', 'Tead2', 'Ran', 'Ung', 'Cdt1', 'Chaf1b', 'Tuba1b', 'Dhfr', 'Rmi2', 'Ranbp1', 'Atad5', 'Topbp1', 'Zgrf1', 'Chaf1a', 'Cenph', 'Gm17057', 'Cenpp', 'Neil3', '2810459M11Rik', 'Ccne2', 'Casp7', 'Kif15', 'Esco2', 'Kif23', 'Cdca2', 'Mis18bp1', 'Spc24', 'Pbk', 'Cdca3', 'Aurkb', 'Kif4', 'Foxm1', 'Pimreg', 'Knstrn', 'Sgo1', 'Ndufa12', 'Fam118a', 'Iqgap1', 'Adhfe1', '9430041J12Rik', 'Lgi4', 'Klf15', 'Ttk', 'Kif18a', 'Tacc3', 'Dnajc9', 'Mfhas1', 'Sptbn2', 'Zhx3', 'Mir124a-1hg', 'Nfasc', 'Mfap4', 'Apc2', 'Znrf2', 'Cbfa2t2', 'Lsm2', 'Cbx7', 'Rlbp1', 'Hes5', 'Pif1', 'Cdc20', 'Kdm5b', '4933408B17Rik', 'Ccnb2', 'Usp24', 'Acyp2', 'Arrb1', 'Tcf19', 'Lig1', 'Slbp', 'Kif24', 'Klhl40', 'Cep126', 'Rad51', 'Tk1', 'Ftx', 'Sclt1', 'Rapgef6', 'Pde3b', 'Upp2', 'Vmn2r2', 'Tipin', 'Siva1', 'Nfat5', 'Clock', 'Elovl6', 'Chd3', 'Fsd1l', 'Plekhf1', 'Pak4', 'Gm16364', 'Bcar1', 'Ap2a1', 'Bcas1os2', 'Gpr146', 'Dusp15', 'Gm14964', 'Mast1', 'Akt3', 'Trafd1', 'Eml6', 'Tubb4a', 'Pacs2', 'Gm35188', 'Rassf10', 'Dct', 'Gm11659', 'Dis3l2', 'Gm49797', 'Wdfy1', 'Tdrd3', 'Phrf1', 'E330009J07Rik', 'Gp1bb', 'Arhgap5', 'Pdcd4', 'Aprt', 'Urm1', 'Bgn', 'Traf4', 'Gm13187', 'Rhbdl2', 'Gipc1', 'Ptger1', 'Med22', 'Plekha1', 'Lrch2', 'Glrb', 'Nol4l', 'Plekhg3', 'Ptpn11', 'Kif13b', 'Acp1', 'Fam83d', 'Tnfaip8l1', 'Tuba1c', 'Arhgef39', 'Fam110a', 'Cdkn3', 'Emp1', 'Gm11457', 'Mzf1', 'Gm19605', 'Kif20b', 'Plk1', 'Cep55', 'Celsr3', 'Svop', 'Atcay', 'AI506816', 'Tgif2', 'Nrarp', '2610301B20Rik', 'Kctd13', 'Gjb1', 'Plin3', 'Klk6', 'Usp31', 'Neat1', 'Kctd3', 'Abcg1', 'Arhgap23', 'E2f2', 'Cdc45', 'Cdc6', 'Tmem121', 'Hist1h1a', 'Hist1h2ae', 'Prr11', 'Mxd3', 'Hist1h4d', 'Srm', 'Dll1', 'Cad', 'AU020206', 'Mettl1', 'Aagab', 'Pus7', 'Pprc1', 'Dusp8', 'Fam214b', 'Nyap1', 'Dop1b', 'Aurka', 'H1f0', 'Arpc3', 'Chd5', 'Nkx2-9', 'Cyp27a1', 'Carns1', 'Fntb', 'Inppl1', 'Dbx2', 'Zfp36l2', 'Igsf8', 'Pdlim2', 'Ccp110', 'Ctps', 'Smurf1', 'Hip1r', 'Gm32633', 'Foxj1', 'Sspo', 'Pld3', 'Mcm4', 'Ampd3', 'Zfp367', 'Blm', 'Mcm3', 'Rrm1', 'Sema4f', 'St8sia3', 'Gjc2', 'Tssc4', 'Birc2', 'Mroh3', 'Marveld1', 'Il23a', 'Bola3', 'Tanc2', 'Nedd4', 'Hmgn1', 'Ndufc2', 'Ube2s', 'Ptprs', 'Eif1b', 'Fyn', 'Pde4dip', 'Dynll2', 'Tspan3', 'Hspe1', 'Inava', 'A930009A15Rik', 'Cyp2j9', 'Fermt2', 'Flnb', '4930420G21Rik', 'Aplp1', 'Scd2', 'Tmem229a', 'Cers2', 'Daam1', 'Evi2a', 'Rinl', 'Zdhhc9', 'Gpr62', 'Glis2', 'Atp6v0e', 'Ssh2', 'Hnrnpa1', 'Hnrnpab', 'Cask', 'Lsm3', 'Gm47283', 'Snrpg', 'Rpl10', 'Rpl35', 'Rack1', 'Fars2', 'Sacs', 'Cpd', 'A630089N07Rik', '4632427E13Rik', 'Stx6', 'Eml4', 'Snhg1', 'Ybx3', 'Soga3', 'Bcl7a', 'Ttyh3', 'Slc47a1', 'Thbd', 'Slc26a2', 'Prg4', 'Abcb1a', 'Foxd1', 'Igf2', 'Ogn', 'Slc6a20a', 'Cfh', 'Ifitm1', 'Slc13a4', 'Slc22a8', 'Gjb6', 'Prelp', 'Col3a1', 'Gjb2', 'Alpl', 'Vcam1', 'Serpinh1', 'Ifitm3', 'Lyz2', 'Stab1', 'C1qa', 'C1qc', 'Csf1r', 'Pf4', 'Tyrobp', 'C1qb', 'Fcer1g', 'Laptm5', 'P2rx7', 'Txnip', 'Ptpn18', 'Zfp36', 'Ms4a6c', 'Plek', 'Il1rl1', 'Itk', 'Mir142hg', 'Il7r', 'Il2ra', 'Srgn', 'Tnfaip3', 'Birc3', 'Cd52', 'Rac2', 'Gm2682', 'Ms4a4b', 'Gimap3', 'AW112010', 'Cd3g', 'Ltb', 'Hcst', 'Gm26740', 'Nkg7', 'Fyb', 'Ccl5', 'Il2rb', 'Arhgap45', 'Clnk', 'Klrk1', 'Gimap4', 'Cd79b', 'Bank1', 'H2-Eb1', 'Apobec3', 'Cd37', 'Iglc2', 'S100a9', 'Il1b', 'Csf3r', 'S100a8', 'Ncf2', 'Alox5ap', 'Klf2', 'Fgr', 'H2-Aa', 'Plbd1', 'Mpeg1', 'Inpp5d', 'Ccr2', 'Tnip3', 'H2-DMb1', 'Cd209a', 'Gm34838', 'Cmtm5', 'Hmgcs2', 'H2-DMa', 'Wfdc17', '2310022B05Rik', 'Cx3cr1', 'Selplg', 'Tmem119', 'Ly86', 'Gpr34', 'Hexb', 'Vsir', 'Slco2b1', 'Aqp1', 'Higd1b', 'Vtn', 'Ndufa4l2', 'Adap2', 'Notch3', 'Myl9', 'Acta2', 'Tagln', 'Myh11', 'Flna', 'Ly6c1', 'Cldn5', 'Ly6a', 'Slco1a4', 'Slc2a1', 'Pltp', 'Tbx15', 'Slc22a6', 'Fcgr3', 'Psmb8', 'Vstm4', 'Slc38a2', 'Siglech', 'Lmod1', 'Unc93b1', 'Fcrls', 'Ctsd', 'Rab43', 'Wtip', 'Rhob', 'Ephb4', 'Hey2', 'Cnn1', 'Plpp1', 'Gpam', 'Mppe1', 'Thpo', 'Hhipl1', 'Nudt12', 'Alg8', 'Sycp2', 'Amigo1', 'Naa10', 'Arhgap27', '4930432B10Rik', 'Acvr2b', 'Ggt7', 'Gm30551', 'Anp32e', 'Endov', 'Mettl7a1', 'Tmem235', 'Slc25a39', 'Grn', 'Cfap300', 'Il2rg', 'Itgal', 'Slc6a6', 'Arhgap21', 'Aatk', 'Ctsb', 'Plekha4', 'Sdc4', 'Serinc3', 'Slc27a1', 'Ralgps2', 'Dennd4a', 'Bsg', 'Tsc22d1', 'Josd2', 'S1pr5', 'Ctso', 'Gm26834', 'Vps37b', 'Tbc1d32', 'Gm16029', 'Mfsd7a', 'Lap3', 'Prr18', 'Fgfbp1', 'Anxa8', 'Kcnj13', 'Tspan8', 'Fam207a', 'Eogt', 'Dhtkd1', 'Wnt6', 'Angptl2', 'Psme2', 'Slc22a2', 'Plscr2', 'Serpind1', 'Slc6a12', 'Fam180a', 'Pik3ap1', 'Spo11', 'Man1a2', 'Tmod2', 'Megf9', 'Hspa14', 'Slc1a5', 'Htra3', 'Clec3b', 'D630003M21Rik', 'Mfap5', 'Entpd2', 'Lbp', 'Npdc1', 'Rarres2', 'Sptbn1', 'Vamp5', 'Ccl19', 'Dpysl2', 'Anks3', 'Lrrc29', 'Lrrc24', 'Emcn', 'Dpep1', 'Inmt', 'Gata6', 'Mrap', 'Cd38', 'Kmt5a', 'Myo18a', 'Phc1', 'Micall1', 'Nipal4', 'Fcnaos', 'Snx18', 'Orai1', 'Pnpla3', '2810457G06Rik', 'Rab32', 'Cpxm1', 'Irf1', 'Wnk2', 'Cmklr1', 'Cdc42ep2', 'Gm36975', 'Myl12a', 'Snhg6', 'Mrpl57', 'Sbf2', 'Itsn1', 'Cbr2', 'Snx24', 'Myo5a', 'Cybb', 'Ccl2', 'Cd14', 'Socs3', 'Mpz', 'Dhh', 'Lyve1', 'Ltc4s', 'Ifi207', 'Cd163', 'Gm20186', 'Ifrd1', 'Furin', 'Rpl10a', 'Mcf2l', 'Agt', 'Pald1', 'Slc43a3', 'Cd3d', 'Cd3e', 'Lck', 'Ms4a6b', 'Cd28', 'Cd2', '9930111J21Rik2', 'Themis', 'Cd6', 'Lat', 'Icos', 'Kcnn4', 'Tcf7', 'Sh2d1a', 'Cd226', 'Ptprcap', 'Gm36823', 'Kcnj8', 'Adap2os', 'Klrd1', 'Klre1', 'Cd244a', 'Klrb1c', 'Ncr1', 'Myo1f', 'Xcl1', 'Atp8b4', 'Cd7', 'Klrc2', 'Ccl4', 'Gzmb', 'Ugcg', 'Ptpn22', 'H2-Ob', 'Ighd', 'Blk', 'Arhgef18', 'Iglc3', 'BE692007', 'Chst3', 'Map3k7cl', 'Olfr558', 'Adgre5', 'Il1r2', 'Itgam', 'Spi1', 'Cxcr2', 'Mmp9', 'Hp', 'Retnlg', 'Mxd1', 'Clec4d', 'Slpi', 'C5ar1', 'Tinagl1', 'Cysltr2', 'Aspn', 'Dstn', 'Xcr1', 'Ciita', 'Clec9a', 'Zfp366', 'Tlr3', 'Jaml', 'Gcsam', 'Ifi205', 'Rab7b', 'Ifi211', 'Ptgis', 'Serpine1', 'Actg2', '2200002D01Rik', 'Neil2', 'Ccl9', 'Ccl6', 'S100a4', 'Lilrb4a', 'Lilr4b', 'Axl', 'Capg', 'Retnla', 'C3ar1', 'Cxcl2', 'Rgs1', 'Cyp4f18', 'Gkn3', 'Bmx', 'Sema3g', 'Ehd2', 'Amd1', 'Mannr', 'Trpv4', 'Gm9946', 'Gpcpd1', 'Pknox1', 'Tfrc', 'Ctla2a', 'Fmo2', 'Slc38a5', 'Pten', 'Ctsh', 'Fcgr2b', 'Ank', 'Kmo', 'Ccl17', 'Siglecg', '5830428M24Rik', 'Cd209c', 'H2-Oa', 'Csad', 'Ccr5', 'Abi3', 'Trem2', 'Itgb4', 'Msln', 'A930007I19Rik', '1700008O03Rik', 'Mical3', 'Sept11', 'Foxc1', 'Alx3', 'Cdh5', 'Dmrt3', 'Tfap2e', 'Gys1', 'Plrg1', 'Dffa', 'Rtkn', 'Gm28154', 'Gm32834', 'A330040F15Rik', 'Fam43b', 'Plk3', 'Gm28653', 'Rtl6', 'Tmc4', 'AV356131', 'Slc49a4', 'Zfp72', 'Slc18b1', 'Fam217b', 'Rsad1', 'Sord', 'Gm30400', 'Dhrs1', 'Gpat3', 'Tomm34', 'A330074K22Rik', 'Wdr27', 'Stoml1', 'P4ha1', 'Tmem8', 'Snn', 'Llph', 'Ganc', 'Pcyt1b', 'Gcdh', 'Psme1', 'Smim10l2a', 'Abcf2', 'Carmil2', 'Abhd11', 'Borcs5', 'Reep3', 'Gm33373', 'A430005L14Rik', 'Gm31508', 'Mtpap', 'Prdm11', 'Mov10', 'Gstz1', 'Mettl14', '0610009B22Rik', 'Scyl3', 'Tnip1', 'Arhgap4', 'Pdlim7', 'Shc2', '1700057H15Rik', 'Samd7', 'Gm49492', 'Gm45589', 'Krt7', 'Olfr1191-ps1', 'Gprin2', 'Gm49698', 'Gm2415', 'Vsig10', 'Arrdc1', '1700052K11Rik', '4930568G15Rik', 'Dnmt3l', 'Trim45', 'Hsf4', 'A330033J07Rik', '4933425B07Rik', 'Olfr48', 'AW047730', 'Dao', 'Gm6145', 'Tprkb', 'Myoc', 'Phkg1', 'Slc7a10', 'Atoh7', 'Sycp1', 'Cep76', 'C230072F16Rik', 'Etnppl', 'Slc6a9', 'Icmt', 'C4b', 'Slc45a4', 'Nsmce4a', 'Six4', 'Meis3', 'Csk', 'Nsdhl', 'Gm32219', 'Hes3', 'Ttll3', 'Sri', 'Cat', 'Lypla2', 'Cd151', 'Cep131', 'Pqlc1', 'Ankrd52', 'Atl2', 'Mrpl10', 'Tmem19', 'Dennd6b', '6430553K19Rik', 'Ankrd34a', 'Tmem50b', 'Rab39b', 'Rnf19b', 'Arhgef4', 'Cxcl5', 'Hif3a', 'Ccdc170', 'Cyp4f15', 'Acsl3', 'Lcat', 'Itih3', 'Gm35552', 'Ppp1r3c', 'Paqr6', 'Eva1a', 'Phyhd1', 'Fmn2', 'Psd', 'Dact3', '4930488L21Rik', 'Prnp', 'Glud1', 'Sync', 'Tnfsf12', 'Rcn2', 'Nkrf', 'Cacfd1', 'Gm5294', 'Smc2os', 'Zfp40', 'Cfap410', 'Dennd3', 'Reep1', 'Btbd17', 'Apln', 'Kif5a', 'Neurl1a', 'Agap2', 'Gapdh', 'Ccdc34', 'Arf3', 'Rps9', 'Prpsap1', 'Slc36a2', 'Ttc8', 'Chic2', 'Rpl5', 'Enpp4', 'Nemp1', 'Catsper3', 'Pigk', '6530411M01Rik', 'Ralgps1', 'Papss2', 'Fzd2', 'Ugp2', 'Tomm7', 'Ost4', 'Uba52', 'Fam227b', 'Flvcr1', 'Lamp1', '5031439G07Rik', 'Pink1', 'Pfdn2', 'Ids', 'Slc43a2', 'Flnc', 'Sema3b', 'Atoh8', 'Mtch1', 'Cmss1', 'Hcfc1r1', 'Cntf', 'Gm6277', 'Gm27016', 'Gm28750', 'Cst12', 'Gm29571', 'Gm10684', 'Tlr4', 'Pgam2', 'Ccdc122', 'Tspan10', 'Gpx6', 'Lrrc52', 'Tcirg1', 'Psmd5', 'Hsbp1', 'Anapc13', 'Mrps33', 'Ndufb2', 'Rnf7', 'Ndufaf8', '0610012G03Rik', 'Tomm5', 'Lamtor2', 'Ppdpf', 'Mrps36', 'Fbxl16', 'Ctnnb1', 'Ghitm', 'Rps10', 'Rpl36a', 'Smad6', 'Cox10', '5031425E22Rik', 'Trp53inp2', 'Fzd9', 'Fchsd1', 'Asxl2', 'Uggt2', 'Zfp609', 'Supt3', 'Canx', 'D130040H23Rik', 'BC005561', 'Myorg', 'Luc7l2', 'Rbm4b', 'Nme7', 'Triobp', 'Rubcnl', 'Fam57b', '4930488N15Rik', '8030451O07Rik', 'Gm26917', 'Utp14b', 'Slc25a34', 'Kcne1l', 'Washc2', 'Nrros', '5330438D12Rik', 'Frk', '4930401C15Rik', 'Plekhm3', 'Gm19522', 'Crtc3', 'Pard3bos1', 'Gm14697', 'Aox1', 'Gm32004', 'Arhgap9', 'A430090L17Rik', 'Ddi1', 'Gm44788', 'Pnpla7', 'Cep85l', 'Limk2', 'Chd9', 'Chchd3', 'Hr', 'Tbx2', 'Tex22', 'Lpar3', 'Car14', 'A330087D11Rik', 'Lpo', 'Tbc1d10a', 'Trp63', 'Col11a2', 'Pgm1', 'Rnf215', 'Idh2', 'Haus3', 'Atpif1', 'Gm38576', 'Galm', 'Gm34105', 'Cd82', 'Nuf2', 'Spry3', 'Cercam', 'Mpv17l2', 'Gm39323', 'Kcnmb1', 'Pih1h3b', 'Gm42681', 'Atp5md', 'Them4', 'Arxes2', 'Cdc42ep4', 'Ppp1r9b', '9330159F19Rik', 'Ak7', 'Rsph1', 'Cfap43', 'Tmem212', 'Unc5cl', '3300002A11Rik', 'Ccdc146', 'Fam216b', 'Wdr63', 'Cfap126', '1700007K13Rik', '2010001K21Rik', 'Wfdc2', 'Acsf2', 'Wt1', 'Pnp', '2900040C04Rik', 'Slc4a5', 'Folr1', 'Kcne2', 'Calml4', '2410004P03Rik', 'Gm16201', 'Elof1', 'Tbc1d9', 'Spata17', 'Fndc3c1', 'Spp2', 'Tmem107', 'Kctd14', 'Rax', 'Rpn2', 'Cab39l', 'Cldn3', 'Slc22a17', 'Luc7l3', 'Hfe', 'Psenen', 'Atp6v1g1', 'Atp7b', 'Ccdc180', 'Dnah3', 'AC160336.1', 'Wt1os', 'Kif27', 'Wdr78', 'Grcc10', '1700088E04Rik', 'Ttc21a', 'Slc20a2', 'Apobec2', 'Ankub1', 'Crocc2', '1700024G13Rik', 'Odf3b', 'Crocc', 'Rassf9', 'Bbox1', 'Tnnt3', 'Jakmip1', 'Vmn2r30', 'Gm20383', 'Gm29538', 'Dthd1', 'Lrrc71', 'Lrrc36', 'Ect2l', 'Sntn', 'Rp1', 'Acot6', 'Myb', 'Stoml3', 'Car9', 'Uox', 'Cdhr4', 'Ankrd66', 'Ccdc78', 'BC051019', 'Musk', 'Cdh26', '1700020G17Rik', 'Nlrp3', 'Ppfia3', 'Iqca', 'Plet1', 'Serpinb1a', 'Helz', 'Lhfpl4', '1700012P22Rik', 'Rbm42', 'Ttll10', 'Mllt6', 'Snx4', 'Thap11', 'Gm44109', 'Tarsl2', 'Gm49896', 'Gprc5c', 'Rnft1', 'Gm47888', 'Ttll8', 'Gm20083', '1700019G24Rik', 'Krt15', 'Cuzd1', 'Muc19', 'Prr29', 'Slain2', 'Slc11a2', 'Gm26671', 'Azin2', 'Slc26a3', 'Ctdnep1', 'Stx7', 'Ncoa4', 'Gm40761', 'Fam126b', 'Spdef', 'Ldlrad2', 'Nes', 'Gli1', 'Cfap65', 'Cstdc2', 'Tmem52', 'Taf13', 'Crygn', 'Rbp2', 'Sap30bpos', 'Gm12326', 'Hist1h4h', 'Gm48050', 'Plxnb2', 'Rd3', 'Abi1', 'Smap1', 'Abi2', 'Stt3a', 'Clasp1', 'Npc1', 'Inpp4a', 'Map3k3', 'Ikzf5', 'Adprh', 'Usp15', 'Bdp1', 'Ap3m1', 'C1qtnf3', 'Gm38562', 'Cacna1s', 'Gm44386', 'Slc25a21', 'Got1l1', 'Gm16160', 'Ccdc33', '4833427G06Rik', '4930522L14Rik', 'Gm36033', 'Ep400', 'Nsf', 'Fbxl13', 'Gm49417', 'Gm48898', 'Aoc1', 'Aass'
    ] 
    return imputed_genes

def slice_index_dict():
    """
    Create a mapping of the brain section label to the corresponding slice index in the 3D image.

    Returns:
    --------
    slice_index_map : dict
        A mapping of the brain section label to the corresponding slice index in the 3D image.
    """
    slice_index_map = {
    "C57BL6J-638850.05": 4,
    "C57BL6J-638850.06": 5,
    "C57BL6J-638850.08": 7,
    "C57BL6J-638850.09": 8,
    "C57BL6J-638850.10": 9,
    "C57BL6J-638850.11": 10,
    "C57BL6J-638850.12": 11,
    "C57BL6J-638850.13": 12,
    "C57BL6J-638850.14": 13,
    "C57BL6J-638850.15": 14,
    "C57BL6J-638850.16": 15,
    "C57BL6J-638850.17": 16,
    "C57BL6J-638850.18": 17,
    "C57BL6J-638850.19": 18,
    "C57BL6J-638850.24": 19,
    "C57BL6J-638850.25": 20,
    "C57BL6J-638850.26": 21,
    "C57BL6J-638850.27": 22,
    "C57BL6J-638850.28": 23,
    "C57BL6J-638850.29": 24,
    "C57BL6J-638850.30": 25,
    "C57BL6J-638850.31": 27,
    "C57BL6J-638850.32": 28,
    "C57BL6J-638850.33": 29,
    "C57BL6J-638850.35": 31,
    "C57BL6J-638850.36": 32,
    "C57BL6J-638850.37": 33,
    "C57BL6J-638850.38": 34,
    "C57BL6J-638850.39": 35,
    "C57BL6J-638850.40": 36,
    "C57BL6J-638850.42": 38,
    "C57BL6J-638850.43": 39,
    "C57BL6J-638850.44": 40,
    "C57BL6J-638850.45": 41,
    "C57BL6J-638850.46": 42,
    "C57BL6J-638850.47": 44,
    "C57BL6J-638850.48": 45,
    "C57BL6J-638850.49": 46,
    "C57BL6J-638850.50": 47,
    "C57BL6J-638850.51": 48,
    "C57BL6J-638850.52": 49,
    "C57BL6J-638850.54": 51,
    "C57BL6J-638850.55": 52,
    "C57BL6J-638850.56": 54,
    "C57BL6J-638850.57": 55,
    "C57BL6J-638850.58": 56,
    "C57BL6J-638850.59": 57,
    "C57BL6J-638850.60": 59,
    "C57BL6J-638850.61": 60,
    "C57BL6J-638850.62": 61,
    "C57BL6J-638850.64": 65,
    "C57BL6J-638850.66": 69,
    "C57BL6J-638850.67": 71
    }
    return slice_index_map

def section_to_zindex(brain_section_label):
    """
    Convert the brain section label to the corresponding slice index in the 3D image.

    Parameters:
    -----------
    brain_section_label : str
        The brain section label (e.g. 'C57BL6J-638850.05').

    Returns:
    --------
    zindex : int
        The corresponding slice index in the 3D image.
    """
    slice_index_map = slice_index_dict()

    if brain_section_label not in slice_index_map:
        return None
    # Lookup the corresponding slice index in the 3D image 
    zindex = slice_index_map[brain_section_label]
    return zindex

def plot_section(xx=None, yy=None, cc=None, val=None, pcmap=None, 
                 overlay=None, extent=None, bcmap=plt.cm.Greys_r, alpha=1.0,
                 fig_width = 6, fig_height = 6):
    """
    Plot the point cloud with an overlay image.

    Parameters:
    -----------
    xx : np.ndarray
        The x-coordinates of the points.
    yy : np.ndarray
        The y-coordinates of the points.
    cc : np.ndarray
        The color of the points.
    val : np.ndarray
        The value of the points.
    pcmap : str
        The primary colormap to use for the point cloud.
    overlay : np.ndarray
        The overlay image.
    extent : tuple
        The extent of the overlay image.
    bcmap : str
        The colormap to use for the boundary overlay.
    alpha : float
        The transparency of the overlay image.
    fig_width : float
        The width of the figure.
    fig_height : float
        The height of the figure.

    Returns:
    --------
    fig : matplotlib.figure.Figure
        The figure object.
    ax : matplotlib.axes._axes.Axes
        The axis object.
    """
    
    fig, ax = plt.subplots()
    fig.set_size_inches(fig_width, fig_height)

    if xx is not None and yy is not None and pcmap is not None:
        plt.scatter(xx, yy, s=0.5, c=val, marker='.', cmap=pcmap)
    elif xx is not None and yy is not None and cc is not None:
        plt.scatter(xx, yy, s=0.5, color=cc, marker='.', zorder=1)   
        
    if overlay is not None and extent is not None and bcmap is not None:
        plt.imshow(overlay, cmap=bcmap, extent=extent, alpha=alpha, zorder=2)
        
    ax.set_ylim(11, 0)
    ax.set_xlim(0, 11)
    ax.axis('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    
    return fig, ax

# Generate a 2D image from points
def points_to_img_sum(points_ndarray, x_size=1100, y_size=1100, pixel_size=10):
    """
    Generates a 2D image slice by summing the expression values of all cells in each pixel.
    
    Parameters:
    -----------
    points_ndarray : np.ndarray
        A 2D ndarray containing the x, y coordinates of cells as well as expression values.
    
    x_size : int, optional
        The size of the image along the x-axis. Default is 1100.

    y_size : int, optional
        The size of the image along the y-axis. Default is 1100.

    pixel_size : int, optional
        The size of each pixel in microns. Default is 10.

    Returns:
    --------
    img : np.ndarray
        A 2D ndarray representing the image slice.
    """
    # Create an empty image of the desired size (1100 x 1100)
    img = np.zeros((y_size, x_size))

    # Swap X and Y coordinates if necessary
    swapped_points_ndarray = points_ndarray[:, [1, 0, 2]]  # Swap X and Y

    # Convert coordinates to pixel indices based on the voxel size
    x_indices = ((swapped_points_ndarray[:, 0]) / (pixel_size / 1000)).astype(int)
    y_indices = ((swapped_points_ndarray[:, 1]) / (pixel_size / 1000)).astype(int)

    # Ensure pixel indices are within bounds of the image
    valid_mask = (x_indices >= 0) & (x_indices < x_size) & (y_indices >= 0) & (y_indices < y_size)
    x_indices = x_indices[valid_mask]
    y_indices = y_indices[valid_mask]
    values = swapped_points_ndarray[:, 2][valid_mask]  # expression values

    # Increment the voxel value for each point's coordinates
    for x, y, value in zip(x_indices, y_indices, values):
        img[y, x] += value

    return img

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    # Load the cell metadata
    cell_df = load_cell_metadata(download_base)

    # Add the reconstructed coordinates to the cell metadata
    cell_df_joined = join_reconstructed_coords(cell_df, download_base)

    # Add the classification levels and the corresponding color.
    cell_df_joined = join_cluster_details(cell_df_joined, download_base)

    # Add the cluster colors
    cell_df_joined = join_cluster_colors(cell_df_joined, download_base)
    
    # Add the parcellation annotation
    cell_df_joined = join_parcellation_annotation(cell_df_joined, download_base)

    # Add the parcellation color
    cell_df_joined = join_parcellation_color(cell_df_joined, download_base)

    # Filter for a specific brain section
    section = filter_brain_section(cell_df_joined, args.slice)

    # Load the region boundaries
    annotation_boundary_array, extent = load_region_boundaries(download_base)
    
    # Get the z index for the specified brain section
    brain_section = f'C57BL6J-638850.{args.slice}'
    zindex = section_to_zindex(brain_section)
    if zindex is None:
        print(f"\n    [red1]Error: Brain section {brain_section} not found\n")
        return

    # Get the boundary slice for the specified brain section
    boundary_slice = annotation_boundary_array[zindex, :, :]

    if args.gene is not None:
        # Load the expression data for all genes (if the gene is in the dataset) 
        adata = load_expression_data(download_base, args.gene, imputed=args.imputed)

        # Filter expression data for the specified gene
        asubset, gf = filter_expression_data(adata, args.gene)

        # Create a dataframe with the expression data for the specified gene
        exp_df = create_expression_dataframe(asubset, gf, section)

        # Plot the expression data with a wireframe overlay of the annotation boundary
        fig, ax = plot_section(exp_df['x_reconstructed'],
                        exp_df['y_reconstructed'], 
                        val=exp_df[args.gene], 
                        pcmap=plt.cm.magma_r,  # Light color scheme
                        overlay=boundary_slice,
                        extent=extent, 
                        bcmap=plt.cm.Greys,
                        alpha = 1.0*(boundary_slice>0),  # Alpha is 1 where the boundary is present
                        fig_width = 9,
                        fig_height = 9 )
        res = ax.set_title(f"{args.gene} Expression in MERFISH-CCF Space")
        if args.output is not None:
            plt.savefig(args.output, bbox_inches='tight', dpi=300)
        else:
            plt.show()
    elif args.color is not None:
        # Plot color with reconstructed coordinates and overlay of the annotation boundary
        fig, ax = plot_section(xx=section['x_reconstructed'],
                            yy=section['y_reconstructed'], 
                            cc=section[args.color],
                            overlay=boundary_slice,
                            extent=extent,
                            bcmap=plt.cm.Greys,
                            alpha=1.0*(boundary_slice>0),
                            fig_width=9,
                            fig_height=9 )
        res = ax.set_title(f"{args.color} in MERFISH-CCF Space")
        if args.output is not None:
            plt.savefig(args.output, bbox_inches='tight', dpi=300)
        else:
            plt.show()
    else:
        print(f"\n    [red1]Error: Please specify either a gene or a color\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()
