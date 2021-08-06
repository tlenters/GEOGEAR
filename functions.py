import os
import pandas as pd
import shutil
import fnmatch
from prov.model import ProvDocument
import prov.model
import glob
import contextlib
import logging
from tqdm.notebook import tqdm
from time import time
from datetime import datetime
import pyproj
import geopandas as gpd
import rasterio
import copy
from google_drive_downloader import GoogleDriveDownloader as gdd

saga_cmd = "saga_cmd"

def url_to_id(url):
    x = url.split("/")
    return x[5]

def download_layers(layer_lst, layer_urls, path):

    for i in range(len(layer_lst)):
        if layer_lst[i].endswith((".zip",".shp")):
            try:
                gdd.download_file_from_google_drive(file_id=url_to_id(layer_urls[i]),
                                                dest_path=path + "/input/" + layer_lst[i], 
                                                overwrite=True, showsize=True, unzip=True)
                os.remove(path+"/input/" + layer_lst[i])
            except IndexError:
                print(layer_lst[i] + " can't be downloaded, check URL...")
                break
        else:
            try:
                gdd.download_file_from_google_drive(file_id=url_to_id(layer_urls[i]),
                                                    dest_path=path+"/input/" + layer_lst[i], 
                                                    overwrite=True, showsize=True)
            except IndexError:
                print(layer_lst[i] + " can't be downloaded, check URL...")

                
    
def grid(mask, cellsize, path):
    
    doc = ProvDocument()
    
    doc.add_namespace('cat', 'https://schemas.isotc211.org/19139/-/cat/1.2')
    doc.add_namespace('gex', 'https://schemas.isotc211.org/19115/-1/gex/1.3')
    doc.add_namespace('msr', 'https://schemas.isotc211.org/19115/-1/msr/1.3/')
    doc.add_namespace('cit', 'https://schemas.isotc211.org/19115/-1/cit/1.3')
    doc.set_default_namespace("")
    
    saga = doc.agent("saga_cmd", (
    (prov.model.PROV_TYPE, 'prov:SoftwareAgent'),
    ('cit:edition', os.popen('saga_cmd --version').read().splitlines()[0])))
    gdal = doc.agent("gdal", (
    (prov.model.PROV_TYPE, 'prov:SoftwareAgent'),
    ('cit:edition', os.popen('ogrinfo --version').read().splitlines()[0])))
    
    if not os.path.exists(path + '/output/grid'): os.makedirs(path + '/output/grid')
    
    mask.to_file(path + "/input/mask.gpkg", driver="GPKG")
    mask_bbox = mask.total_bounds
    
    gg_act = doc.activity('grid_gridding_0_' + str(time())) 

    gg_act.set_time(startTime=datetime.now())
    os.system(saga_cmd 
              + ' grid_gridding 0 -INPUT ' + path + '/input/mask.gpkg -GRID ' + path + '/output/grid/grid.tif -OUTPUT 0 -GRID_TYPE 1 -TARGET_DEFINITION 0 -TARGET_USER_SIZE ' + str(cellsize)
              + " -TARGET_USER_XMIN " + str(mask_bbox[0] - 0.5*int(cellsize))
              + " -TARGET_USER_YMIN " + str(mask_bbox[1] - 0.5*int(cellsize))
              + " -TARGET_USER_XMAX " + str(mask_bbox[2] - 0.5*int(cellsize))
              + " -TARGET_USER_YMAX " + str(mask_bbox[3] - 0.5*int(cellsize)))
    
    
    mask_ent = doc.entity('mask.gpkg', (
        (prov.model.PROV_TYPE, mask.type[0]), 
        ('cat:CT_CRS', str(mask.crs)), 
        ('gex:EX_GeographicBoundingBox', str(mask_bbox))))
    cz_ent = doc.entity('msr:resolution', (
        (prov.model.PROV_TYPE, mask.crs.axis_info[0].unit_name),
        (prov.model.PROV_VALUE, cellsize)))
    doc.used(gg_act, cz_ent)
    doc.used(gg_act, mask_ent)
    doc.wasGeneratedBy(doc.entity('grid.tif'), gg_act)
    doc.wasAssociatedWith(gg_act, saga)
    gg_act.set_time(endTime=datetime.now())
    
    trans_act = doc.activity('gdal_translate_' + str(time()))
    trans_act.set_time(startTime=datetime.now())    
    os.system("gdal_translate " + path + "/output/grid/grid.tif " + path + "/analysis/grid.xyz")
    doc.wasGeneratedBy(doc.entity('grid.xyz'), trans_act)
    doc.used(trans_act, doc.entity("grid.tif"))
    doc.wasAssociatedWith(trans_act, gdal)
    trans_act.set_time(endTime=datetime.now())
    
    grid_xyz = pd.read_csv(path + "/analysis/grid.xyz", header=None, delimiter=" ")
    grid_sub = grid_xyz[(grid_xyz[2] != 0)]
    grid_sub['cell_ID'] = range(1,len(grid_sub)+1)
    grid_rm = grid_sub.drop(2, axis='columns').rename(columns={0:"x",1:"y"})
    grid_rm.to_csv(path + "/output/grid/grid.csv", index=False)
    doc.wasDerivedFrom(doc.entity('grid.csv'), doc.entity('grid.xyz'))
    
    return doc


            
def coverages(layers, projection, path):
    
    doc = ProvDocument()
    
    doc.add_namespace('cat', 'https://schemas.isotc211.org/19139/-/cat/1.2')
    doc.add_namespace('gex', 'https://schemas.isotc211.org/19115/-1/gex/1.3')
    doc.add_namespace('msr', 'https://schemas.isotc211.org/19115/-1/msr/1.3/')
    doc.add_namespace('cit', 'https://schemas.isotc211.org/19115/-1/cit/1.3')
    doc.set_default_namespace("")
    
    saga = doc.agent("saga_cmd", (
        (prov.model.PROV_TYPE, 'prov:SoftwareAgent'),
        ('cit:edition', os.popen('saga_cmd --version').read().splitlines()[0])))
    gdal = doc.agent("gdal", (
        (prov.model.PROV_TYPE, 'prov:SoftwareAgent'),
        ('cit:edition', os.popen('ogrinfo --version').read().splitlines()[0])))
    
    if not os.path.exists(os.path.join(path,'output/coverages')): os.makedirs(os.path.join(path,'output/coverages'))
    
    layers.sort()
    layer_names = []
    layer_lst = []
    layer_urls = []
    for i in layers:
        layer_names.append(os.path.splitext(i[0])[0])
        layer_lst.append(i[0])
        layer_urls.append(i[1])
    
    download_layers(layer_lst, layer_urls, path)
    
    t = tqdm(range(len(layer_lst)))
    
    for i in t:
        if layer_lst[i].endswith(".tif") == False:
            
            lyr = gpd.read_file(path + "/input/" + layer_lst[i])
            lyr_ent = doc.entity(layer_lst[i], (
                (prov.model.PROV_TYPE, lyr.type[0]),
                ('cat:CT_CRS', str(lyr.crs.to_proj4())),
                ('gex:EX_GeographicBoundingBox', str(lyr.total_bounds)),
                ('cit:CI_OnlineResource', layer_urls[i])))
            proj_ent = doc.entity('projection', (
                (prov.model.PROV_TYPE, 'proj4string'),
                (prov.model.PROV_VALUE, str(projection))))

            proj_shp_act = doc.activity('pj_proj4_2_' + str(time()))
            proj_shp_act.set_time(startTime=datetime.now())
            t.set_description("Reprojecting "+ layer_names[i], refresh=True)
            os.system(saga_cmd
            + " -f=p pj_proj4 2 -CRS_PROJ4 "+ projection
            + " -SOURCE " + path + "/input/" + layer_lst[i]
            + " -TARGET " + path + "/analysis/" + layer_names[i] + "_cov_reproj.gpkg -PARALLEL 1")

            doc.wasGeneratedBy(doc.entity(layer_names[i]+'_cov_reproj.gpkg'), proj_shp_act)
            doc.used(proj_shp_act, lyr_ent)
            doc.used(proj_shp_act, proj_ent)
            doc.wasAssociatedWith(proj_shp_act, saga)
            proj_shp_act.set_time(endTime=datetime.now())

            rstr_act = doc.activity('grid_gridding_0_' + str(time()))
            rstr_act.set_time(startTime=datetime.now())
            t.set_description("Rasterizing "+ layer_names[i], refresh=True)
            os.system(saga_cmd
            + " grid_gridding 0 -INPUT " + path + "/analysis/" + layer_names[i] + "_cov_reproj.gpkg"
            + " -GRID " + path + "/analysis/" + layer_names[i] + "_cov_raster.tif -TARGET_USER_SIZE 100")

            doc.wasGeneratedBy(doc.entity(layer_names[i]+'_cov_raster.tif'), rstr_act)
            doc.used(rstr_act, doc.entity(layer_names[i]+'_cov_reproj.gpkg'))
            doc.wasAssociatedWith(rstr_act, saga)
            rstr_act.set_time(endTime=datetime.now())

        else:
            
            lyr = rasterio.open(path + "/input/" + layer_lst[i])
            lyr_ent = doc.entity(layer_lst[i], (
                (prov.model.PROV_TYPE, lyr.meta['driver']),
                ('cat:CT_CRS', str(lyr.crs.to_proj4())),
                ('gex:EX_GeographicBoundingBox', str(list(lyr.bounds[0:4]))),
                ('msr:resolution', lyr.meta['transform'][0]),
                ('cit:CI_OnlineResource', layer_urls[i])))
            proj_ent = doc.entity('projection', (
                (prov.model.PROV_TYPE, 'proj4string'),
                (prov.model.PROV_VALUE, str(projection))))

            proj_rstr_act = doc.activity('pj_proj4_4_' + str(time()))
            proj_rstr_act.set_time(startTime=datetime.now())
            t.set_description("Reprojecting "+ layer_names[i], refresh=True)
            os.system(saga_cmd
            + " pj_proj4 4 -CRS_PROJ4 "+ projection
            + " -SOURCE " + path + "/input/" + layer_lst[i]
            + " -GRID " + path + "/analysis/" + layer_names[i] + "_cov_raster.tif -RESAMPLING 0")

            doc.wasGeneratedBy(layer_names[i]+'_cov_raster.tif', proj_rstr_act)
            doc.used(proj_rstr_act, lyr_ent)
            doc.used(proj_rstr_act, proj_ent)
            doc.wasAssociatedWith(proj_rstr_act, saga)
            proj_rstr_act.set_time(endTime=datetime.now())
            
    raster_lst = []
    raster_names = []
    for i in os.listdir(path + "/analysis"):
        if fnmatch.fnmatch(i, "*_cov_raster.tif"):
            raster_lst.append(i)
            raster_names.append(i.replace("_cov_raster.tif",""))
    
    raster_lst.sort()
    raster_names.sort()
    
    t = tqdm(range(len(raster_lst)))

    for i in t:
        
        calc_cov_act = doc.activity('grid_analysis_26_' + str(time()))
        calc_cov_act.set_time(startTime=datetime.now())
        t.set_description("Calculating coverages of "+ raster_names[i], refresh=True)
        os.system(saga_cmd
        + " grid_analysis 26 -CLASSES " + path + "/analysis/" + raster_lst[i]
        + " -COVERAGES " + path + "/output/coverages/" + raster_names[i] + "_cov_.tif"
        + " -TARGET_DEFINITION 1 -TARGET_TEMPLATE " + path + "/output/grid/grid.tif -DATADEPTH 3")

        doc.wasGeneratedBy(doc.entity(layer_names[i]+'_cov_.tif'), calc_cov_act)
        doc.used(calc_cov_act, doc.entity(raster_lst[i]))
        doc.used(calc_cov_act, doc.entity('grid.tif'))
        doc.wasAssociatedWith(calc_cov_act, saga)
        calc_cov_act.set_time(endTime=datetime.now())

    class_lst = glob.glob(path + "/output/coverages/*cov*tif")

    class_names = []
    for i in class_lst:
        name = os.path.basename(os.path.normpath(i))
        class_names.append(os.path.splitext(name)[0])

    df_total = pd.DataFrame(columns=[0,1,2])

    t = tqdm(range(len(class_lst)))
    
    for i in t:
        t.set_description("Building table for "+ class_names[i], refresh=True)
        os.system("gdal_translate "+class_lst[i]+" " + path + "/analysis/"+class_names[i]+".xyz")
        class_df = pd.read_csv(path + "/analysis/"+class_names[i]+".xyz", header=None, delimiter=" ")
        class_sub = class_df[(class_df[2] != 0)]
        class_sub['feature'] = class_names[i]
        df_total = pd.concat([df_total, class_sub])

    df_rename = df_total.rename(columns={0:'x',1:'y',2:'proportion'})

    
    for i in layer_names:
        trans_act = doc.activity('gdal_translate_' + str(time()))
        trans_act.set_time(startTime=datetime.now())
        doc.wasGeneratedBy(doc.entity(i+'_cov_.xyz'), trans_act)
        doc.used(trans_act, doc.entity(i+"_cov_.tif"))
        doc.wasAssociatedWith(trans_act, gdal)
        trans_act.set_time(endTime=datetime.now())
        
    grid_df = pd.read_csv(path + "/output/grid/grid.csv")

    merge_df = grid_df.merge(df_rename, on=['x','y']).drop(['x','y'], axis='columns')
    merge_df.to_csv(path + "/output/coverages/cov_table.csv", index=False)

    for i in layer_names:
        doc.wasDerivedFrom(doc.entity('cov_table.csv'), doc.entity(i+'_cov_.xyz'))
     
    return doc


    
def resample(layers, projection, path):
    
    doc = ProvDocument()
    
    doc.add_namespace('cat', 'https://schemas.isotc211.org/19139/-/cat/1.2')
    doc.add_namespace('gex', 'https://schemas.isotc211.org/19115/-1/gex/1.3')
    doc.add_namespace('msr', 'https://schemas.isotc211.org/19115/-1/msr/1.3/')
    doc.add_namespace('cit', 'https://schemas.isotc211.org/19115/-1/cit/1.3')
    doc.set_default_namespace("")
    
    saga = doc.agent("saga_cmd", (
    (prov.model.PROV_TYPE, 'prov:SoftwareAgent'),
    ('cit:edition', os.popen('saga_cmd --version').read().splitlines()[0])))
    gdal = doc.agent("gdal", (
    (prov.model.PROV_TYPE, 'prov:SoftwareAgent'),
    ('cit:edition', os.popen('ogrinfo --version').read().splitlines()[0])))
    
    if not os.path.exists(os.path.join(path,'output/resample')): os.makedirs(os.path.join(path,'output/resample'))
    
    layers.sort()
    layer_names = []
    layer_lst = []
    layer_urls = []
    for i in layers:
        layer_names.append(os.path.splitext(i[0])[0])
        layer_lst.append(i[0])
        layer_urls.append(i[1])
    
    download_layers(layer_lst, layer_urls, path)
    
    t = tqdm(range(len(layer_lst)))
    
    for i in t:
        if layer_lst[i].endswith(".tif") == False:
            
            lyr = gpd.read_file(path + "/input/" + layer_lst[i])
            lyr_ent = doc.entity(layer_lst[i], (
                (prov.model.PROV_TYPE, lyr.type[0]),
                ('cat:CT_CRS', str(lyr.crs.to_proj4())),
                ('gex:EX_GeographicBoundingBox', str(lyr.total_bounds)),
                ('cit:CI_OnlineResource', layer_urls[i])))
            proj_ent = doc.entity('projection', (
                (prov.model.PROV_TYPE, 'proj4string'),
                (prov.model.PROV_VALUE, str(projection))))

            proj_shp_act = doc.activity('pj_proj4_2_' + str(time()))
            proj_shp_act.set_time(startTime=datetime.now())
            t.set_description("Reprojecting "+ layer_names[i], refresh=True)
            os.system(saga_cmd
            + " -f=p pj_proj4 2 -CRS_PROJ4 "+ projection
            + " -SOURCE " + path + "/input/" + layer_lst[i]
            + " -TARGET " + path + "/analysis/" + layer_names[i] + "_rsmpl_reproj.gpkg -PARALLEL 1")

            doc.wasGeneratedBy(doc.entity(layer_names[i]+'_rsmpl_reproj.gpkg'), proj_shp_act)
            doc.used(proj_shp_act, lyr_ent)
            doc.used(proj_shp_act, proj_ent)
            doc.wasAssociatedWith(proj_shp_act, saga)
            proj_shp_act.set_time(endTime=datetime.now())

            rstr_act = doc.activity('grid_gridding_0_' + str(time()))
            rstr_act.set_time(startTime=datetime.now())
            t.set_description("Rasterizing "+ layer_names[i], refresh=True)
            os.system(saga_cmd
            + " grid_gridding 0 -INPUT " + path + "/analysis/" + layer_names[i] + "_rsmpl_reproj.gpkg"
            + " -GRID " + path + "/analysis/" + layer_names[i] + "_rsmpl_raster.tif -TARGET_USER_SIZE 100")

            doc.wasGeneratedBy(doc.entity(layer_names[i]+'_rsmpl_raster.tif'), rstr_act)
            doc.used(rstr_act, doc.entity(layer_names[i]+'_rsmpl_reproj.gpkg'))
            doc.wasAssociatedWith(rstr_act, saga)
            rstr_act.set_time(endTime=datetime.now())

        else:
            
            lyr = rasterio.open(path + "/input/" + layer_lst[i])
            lyr_ent = doc.entity(layer_lst[i], (
                (prov.model.PROV_TYPE, lyr.meta['driver']),
                ('cat:CT_CRS', str(lyr.crs.to_proj4())),
                ('gex:EX_GeographicBoundingBox', str(list(lyr.bounds[0:4]))),
                ('msr:resolution', lyr.meta['transform'][0]),
                ('cit:CI_OnlineResource', layer_urls[i])))
            proj_ent = doc.entity('projection', (
                (prov.model.PROV_TYPE, 'proj4string'),
                (prov.model.PROV_VALUE, str(projection))))

            proj_rstr_act = doc.activity('pj_proj4_4_' + str(time()))
            proj_rstr_act.set_time(startTime=datetime.now())
            t.set_description("Reprojecting "+ layer_names[i], refresh=True)
            os.system(saga_cmd
            + " pj_proj4 4 -CRS_PROJ4 "+ projection
            + " -SOURCE " + path + "/input/" + layer_lst[i]
            + " -GRID " + path + "/analysis/" + layer_names[i] + "_rsmpl_raster.tif -RESAMPLING 0")

            doc.wasGeneratedBy(layer_names[i]+'_rsmpl_raster.tif', proj_rstr_act)
            doc.used(proj_rstr_act, lyr_ent)
            doc.used(proj_rstr_act, proj_ent)
            doc.wasAssociatedWith(proj_rstr_act, saga)
            proj_rstr_act.set_time(endTime=datetime.now())
    
    raster_lst = []
    raster_names = []
    for i in os.listdir(path + "/analysis"):
        if fnmatch.fnmatch(i, "*_rsmpl_raster.tif"):
            raster_lst.append(i)
            raster_names.append(i.replace("_rsmpl_raster.tif",""))
    
    raster_lst.sort()
    raster_names.sort()
    
    t = tqdm(range(len(raster_lst)))
    
    for i in t:
        
        rsmpl_act = doc.activity('grid_tools_0_' + str(time()))
        rsmpl_act.set_time(startTime=datetime.now())
        t.set_description("Resampling " + raster_names[i] + " to grid resolution")
        os.system(saga_cmd + ' grid_tools 0 -INPUT ' + path + '/analysis/' + raster_lst[i] +
                  ' -TARGET_TEMPLATE ' + path + '/output/grid/grid.tif' +
                  ' -OUTPUT ' + path + '/output/resample/' + raster_names[i] + '_rsmpl.tif' +
                  ' -TARGET_DEFINITION 1 -SCALE_UP 8 -SCALE_DOWN 0')
        doc.wasGeneratedBy(doc.entity(layer_names[i]+'_rsmpl.tif'), rsmpl_act)
        doc.used(rsmpl_act, doc.entity(raster_lst[i]))
        doc.used(rsmpl_act, doc.entity('grid.tif'))
        doc.wasAssociatedWith(rsmpl_act, saga)
        rsmpl_act.set_time(endTime=datetime.now())
        
    class_lst = glob.glob(path + "/output/resample/*rsmpl*tif")

    class_names = []
    for i in class_lst:
        name = os.path.basename(os.path.normpath(i))
        class_names.append(os.path.splitext(name)[0])

    df_total = pd.DataFrame(columns=[0,1,2])

    t = tqdm(range(len(class_lst)))

    for i in t:
        t.set_description("Building table for "+ class_names[i], refresh=True)
        nodata = rasterio.open(class_lst[i]).nodata
        os.system("gdal_translate "+class_lst[i]+ " " + path + "/analysis/"+class_names[i]+".xyz")
        class_df = pd.read_csv(path + "/analysis/"+class_names[i]+".xyz", header=None, delimiter=" ")
        class_sub = class_df[(class_df[2] != nodata)]
        class_sub['feature'] = class_names[i]
        df_total = pd.concat([df_total, class_sub])

    df_rename = df_total.rename(columns={0:'x',1:'y',2:'value'})


    for i in layer_names:
        trans_act = doc.activity('gdal_translate_' + str(time()))
        trans_act.set_time(startTime=datetime.now())
        doc.wasGeneratedBy(doc.entity(i+'_rsmpl.xyz'), trans_act)
        doc.used(trans_act, doc.entity(i+"_rsmpl.tif"))
        doc.wasAssociatedWith(trans_act, gdal)
        trans_act.set_time(endTime=datetime.now())

    grid_df = pd.read_csv(path + "/output/grid/grid.csv")

    merge_df = grid_df.merge(df_rename, on=['x','y']).drop(['x','y'], axis='columns')
    merge_df.to_csv(path + "/output/resample/rsmpl_table.csv", index=False)

    for i in layer_names:
        doc.wasDerivedFrom(doc.entity('rsmpl_table.csv'), doc.entity(i+'_rsmpl.xyz'))
        
    return doc


        
def presence_absence(layers, projection, path):
    
    doc = ProvDocument()
    
    doc.add_namespace('cat', 'https://schemas.isotc211.org/19139/-/cat/1.2')
    doc.add_namespace('gex', 'https://schemas.isotc211.org/19115/-1/gex/1.3')
    doc.add_namespace('msr', 'https://schemas.isotc211.org/19115/-1/msr/1.3/')
    doc.add_namespace('cit', 'https://schemas.isotc211.org/19115/-1/cit/1.3')
    doc.set_default_namespace("")
    
    saga = doc.agent("saga_cmd", (
    (prov.model.PROV_TYPE, 'prov:SoftwareAgent'),
    ('cit:edition', os.popen('saga_cmd --version').read().splitlines()[0])))
    gdal = doc.agent("gdal", (
    (prov.model.PROV_TYPE, 'prov:SoftwareAgent'),
    ('cit:edition', os.popen('ogrinfo --version').read().splitlines()[0])))
    
    if not os.path.exists(os.path.join(path,'output/presence_absence')): os.makedirs(os.path.join(path,'output/presence_absence'))
    
    layers.sort()
    layer_names = []
    layer_lst = []
    layer_urls = []
    for i in layers:
        layer_names.append(os.path.splitext(i[0])[0])
        layer_lst.append(i[0])
        layer_urls.append(i[1])
    
    download_layers(layer_lst, layer_urls, path)
    
    t = tqdm(range(len(layer_lst)))
    
    for i in t:
        
        lyr = gpd.read_file(path + "/input/" + layer_lst[i])
        lyr_ent = doc.entity(layer_lst[i], (
            (prov.model.PROV_TYPE, lyr.type[0]),
            ('cat:CT_CRS', str(lyr.crs.to_proj4())),
            ('gex:EX_GeographicBoundingBox', str(lyr.total_bounds)),
            ('cit:CI_OnlineResource', layer_urls[i])))
        proj_ent = doc.entity('projection', (
            (prov.model.PROV_TYPE, 'proj4string'),
            (prov.model.PROV_VALUE, str(projection))))

        proj_shp_act = doc.activity('pj_proj4_2_' + str(time()))
        proj_shp_act.set_time(startTime=datetime.now())
        t.set_description("Reprojecting "+ layer_names[i], refresh=True)
        os.system(saga_cmd
        + " -f=p pj_proj4 2 -CRS_PROJ4 "+ projection
        + " -SOURCE " + path + "/input/" + layer_lst[i]
        + " -TARGET " + path + "/analysis/" + layer_names[i] + "_pa_reproj.gpkg -PARALLEL 1")

        doc.wasGeneratedBy(doc.entity(layer_names[i]+'_pa_reproj.gpkg'), proj_shp_act)
        doc.used(proj_shp_act, lyr_ent)
        doc.used(proj_shp_act, proj_ent)
        doc.wasAssociatedWith(proj_shp_act, saga)
        proj_shp_act.set_time(endTime=datetime.now())
        
        pa_act = doc.activity('grid_gridding_0_' + str(time()))
        pa_act.set_time(startTime=datetime.now())
        t.set_description("Calculating "+ layer_names[i] + " point presence-absence", refresh=True)
        os.system(saga_cmd
                 + ' grid_gridding 0 -INPUT ' + path + '/analysis/' + layer_names[i] + '_pa_reproj.gpkg'
                 + ' -TARGET_TEMPLATE ' + path + '/output/grid/grid.tif'
                 + ' -GRID ' + path + '/output/presence_absence/' + layer_names[i] + '_pa.tif '
                 + ' -COUNT ' + path + '/output/presence_absence/' + layer_names[i] + '_count.tif '
                 + ' -OUTPUT 0' 
                 + ' -TARGET_DEFINITION 1')
        doc.wasGeneratedBy(doc.entity(layer_names[i]+'_pa.tif'), pa_act)
        doc.wasGeneratedBy(doc.entity(layer_names[i]+'_count.tif'), pa_act)
        doc.used(pa_act, doc.entity(layer_names[i]+'_pa_reproj.gpkg'))
        doc.used(pa_act, doc.entity('grid.tif'))
        doc.wasAssociatedWith(pa_act, saga)
        pa_act.set_time(endTime=datetime.now())

    class_lst = glob.glob(path + "/output/presence_absence/*tif")

    class_names = []
    for i in class_lst:
        name = os.path.basename(os.path.normpath(i))
        class_names.append(os.path.splitext(name)[0])

    df_total = pd.DataFrame(columns=[0,1,2])

    t = tqdm(range(len(class_lst)))

    for i in t:
        t.set_description("Building table for "+ class_names[i], refresh=True)
        os.system("gdal_translate "+class_lst[i]+" " + path + "/analysis/"+class_names[i]+".xyz")
        class_df = pd.read_csv(path + "/analysis/"+class_names[i]+".xyz", header=None, delimiter=" ")
        class_sub = class_df[(class_df[2] != 0)]
        class_sub['feature'] = class_names[i]
        df_total = pd.concat([df_total, class_sub])

    df_rename = df_total.rename(columns={0:'x',1:'y',2:'value'})


    for i in layer_names:
        trans_act = doc.activity('gdal_translate_' + str(time()))
        trans_act.set_time(startTime=datetime.now())
        doc.wasGeneratedBy(doc.entity(i+'_pa.xyz'), trans_act)
        doc.used(trans_act, doc.entity(i+"_pa.tif"))
        doc.wasAssociatedWith(trans_act, gdal)
        trans_act.set_time(endTime=datetime.now())
        
        trans_act = doc.activity('gdal_translate_' + str(time()))
        trans_act.set_time(startTime=datetime.now())
        doc.wasGeneratedBy(doc.entity(i+'_count.xyz'), trans_act)
        doc.used(trans_act, doc.entity(i+"_count.tif"))
        doc.wasAssociatedWith(trans_act, gdal)
        trans_act.set_time(endTime=datetime.now())       
        
    grid_df = pd.read_csv(path + "/output/grid/grid.csv")

    merge_df = grid_df.merge(df_rename, on=['x','y']).drop(['x','y'], axis='columns')
    merge_df.to_csv(path + "/output/presence_absence/pa_table.csv", index=False)

    for i in layer_names:
        doc.wasDerivedFrom(doc.entity('pa_table.csv'), doc.entity(i+'_pa.xyz'))
        doc.wasDerivedFrom(doc.entity('pa_table.csv'), doc.entity(i+'_count.xyz'))
    
    return doc


        
def grid_statistics(params):
    grid_lst = []
    for i in os.listdir("output"):
        if fnmatch.fnmatch(i, "*.tif"):
            j = 'output/' + i
            grid_lst.append(j)

    grid_str = ";".join(grid_lst)
    
    os.system(saga_cmd 
        + ' statistics_grid 13 -GRIDS output/' + grid_str
        + ' -STATS table.csv' 
        + ' -DATA_CELLS ' + params[0]
        + ' -NODATA_CELLS ' + params[1]
        + ' -CELLSIZE ' + params[2]
        + ' -MEAN ' + params[3]
        + ' -MIN ' + params[4]
        + ' -MAX ' + params[5]
        + ' -RANGE ' + params[6]
        + ' -SUM ' + params[7]
        + ' -SUM2 ' + params[8]
        + ' -VAR ' + params[9]
        + ' -STDDEV ' + params[10]
        + ' -STDDEVLO ' + params[11]
        + ' -STDDEVHI ' + params[12]
        )