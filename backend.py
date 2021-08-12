from functions import coverages, resample, presence_absence
import os
from prov.dot import prov_to_dot
from prov.model import ProvDocument

def analysis(projection, layers_dict, grd_json, path, prov):

    docs = []

    for i in layers_dict.keys():

        if i == "presence_absence":
            layers = []
            for j in layers_dict[i]:
                layers.append(list(j.items())[0])
            docs.append(presence_absence(layers, projection, path))

        elif i == "coverages":
            layers = []
            for j in layers_dict[i]:
                layers.append(list(j.items())[0])
            docs.append(coverages(layers, projection, path))

        elif i == "resample":
            layers = []
            for j in layers_dict[i]:
                layers.append(list(j.items())[0])
            docs.append(resample(layers, projection, path))

            
    grd_doc = ProvDocument.deserialize(content=grd_json)
    
    for i in docs:
        grd_doc.update(i)
    
    
    if not os.path.exists(path + '/output/provenance'): os.makedirs(path + '/output/provenance')

    for i in list(prov):
        if i in ["PNG","PDF"]:
            dot = prov_to_dot(grd_doc, direction="BT")
            if i == "PNG":
                dot.write(path + '/output/provenance/GEOGEAR-prov.png', format='png')
            else:
                dot.write_pdf(path + '/output/provenance/GEOGEAR-prov.pdf', )
        elif i == "JSON":
             grd_doc.serialize(path + '/output/provenance/GEOGEAR-prov.json')
        elif i == "XML":
            grd_doc.serialize(path + '/output/provenance/GEOGEAR-prov.xml', format='xml')
        elif i == "RDF":
            grd_doc.serialize(path + '/output/provenance/GEOGEAR-prov.ttl', format='rdf', rdf_format='ttl')

    return grd_doc