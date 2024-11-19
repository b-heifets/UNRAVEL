#!/usr/bin/env python3

"""
Use ``/Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_ccf_mpl.py`` from UNRAVEL to plot MERFISH data from the Allen Brain Cell Atlas.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/merfish_ccf_registration_tutorial.html#read-in-section-reconstructed-and-ccf-coordinates-for-all-cells
    - The slice index ranges from 05 to 67.
    - Missing slices include: 07 20 21 22 23 34 41 63 65.

Usage for gene:
---------------
    /Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_ccf_mpl.py -b path/to/base_dir -s slice -g gene

Usage for color:
----------------
    /Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_ccf_mpl.py -b path/to/base_dir -s slice -c color
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
    opts.add_argument('-c', '--color', help='Color to plot (e.g., parcellation_substructure_color or neurotransmitter_color', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def load_cell_metadata(download_base):
    """
    Load the cell metadata from the MERFISH data (using cell_label as the index).

    Parameters:
    -----------
    download_base : Path
        The root directory of the MERFISH data.

    Returns:
    --------
    cell_df : pd.DataFrame
        The cell metadata. Columns: 'brain_section_label', 'cluster_alias', 'average_correlation_score',
       'feature_matrix_label', 'donor_label', 'donor_genotype', 'donor_sex',
       'x_section', 'y_section', 'z_section'
    """
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
        The cell metadata joined with the reconstructed coordinates. Added columns: 'x_reconstructed', 'y_reconstructed', 'z_reconstructed',
       'parcellation_index'
    """
    reconstructed_coords_path = download_base / 'metadata/MERFISH-C57BL6J-638850-CCF/20231215/reconstructed_coordinates.csv'
    print(f"\n    Adding reconstructed coordinates from {reconstructed_coords_path}\n")
    reconstructed_coords_df = pd.read_csv(reconstructed_coords_path, dtype={'cell_label': str})
    reconstructed_coords_df.rename(columns={'x': 'x_reconstructed', 'y': 'y_reconstructed', 'z': 'z_reconstructed'}, inplace=True)
    reconstructed_coords_df.set_index('cell_label', inplace=True)
    cell_df_joined = cell_df.join(reconstructed_coords_df, how='inner')
    return cell_df_joined

def join_cluster_details(cell_df_joined, download_base):
    """
    Join the cell metadata with the cluster details and colors (using cluster_alias).

    Parameters:
    -----------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the reconstructed coordinates.
    download_base : Path
        The root directory of the MERFISH data.

    Returns:
    --------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the cluster details and colors. Added columns: 'neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'
    """
    cluster_details_path = download_base / 'metadata/WMB-taxonomy/20231215/views/cluster_to_cluster_annotation_membership_pivoted.csv'
    print(f"\n    Adding cluster details from {cluster_details_path}\n")
    cluster_details = pd.read_csv(cluster_details_path)
    cluster_details.set_index('cluster_alias', inplace=True)
    cell_df_joined = cell_df_joined.join(cluster_details, on='cluster_alias')
    return cell_df_joined

def join_cluster_colors(cell_df_joined, download_base):
    """
    Join the cell metadata with the cluster colors (using cluster_alias).

    Parameters:
    -----------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the cluster details.
    download_base : Path
        The root directory of the MERFISH data.

    Returns:
    --------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the cluster colors. Added columns: 'neurotransmitter_color', 'class_color', 'subclass_color',
       'supertype_color', 'cluster_color'
    """
    cluster_colors_path = download_base / 'metadata/WMB-taxonomy/20231215/views/cluster_to_cluster_annotation_membership_color.csv'
    print(f"\n    Adding cluster colors from {cluster_colors_path}\n")
    cluster_colors = pd.read_csv(cluster_colors_path)
    cluster_colors.set_index('cluster_alias', inplace=True)
    cell_df_joined = cell_df_joined.join(cluster_colors, on='cluster_alias')
    return cell_df_joined

def join_parcellation_annotation(cell_df_joined, download_base):
    """
    Join the cell metadata with the parcellation annotation (using parcellation_index).

    Parameters:
    -----------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the cluster colors.
    download_base : Path
        The root directory of the MERFISH data.

    Returns:
    --------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the parcellation annotation. Added columns: 'parcellation_organ', 'parcellation_category', 'parcellation_division',
       'parcellation_structure', 'parcellation_substructure'
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
    Join the cell metadata with the parcellation color (using parcellation_index).

    Parameters:
    -----------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the parcellation annotation.
    download_base : Path
        The root directory of the MERFISH data.

    Returns:
    --------
    cell_df_joined : pd.DataFrame
        The cell metadata joined with the parcellation color. Added columns: 'parcellation_organ_color', 'parcellation_category_color',
       'parcellation_division_color', 'parcellation_structure_color',
       'parcellation_substructure_color'
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
    Filter the cell metadata for a specific brain section (using brain_section_label).
    
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

def load_expression_data(download_base, gene):
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
    genes_in_merfish = genes_in_merfish_data()

    if gene in genes_in_merfish:
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

    expression_path = download_base / 'expression_matrices/MERFISH-C57BL6J-638850-imputed/20240831/C57BL6J-638850-imputed-log2.h5ad'

    print(f"\n    Loading expression data from {expression_path}\n")

    adata = anndata.read_h5ad(expression_path, backed='r')
    
    # Get list of genes (var) in the expression data
    genes = adata.var.gene_symbol

    print(f'\nImputed genes: \n')

    for gene in genes:
        print(f"'{gene}'delimiter")

    verbose_end_msg()

if __name__ == '__main__':
    main()