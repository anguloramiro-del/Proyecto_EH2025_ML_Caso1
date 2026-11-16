"""Descarga y prepara la capa municipal referencial publicada en Atlas UDAPE2025.

No estima municipios para personas EH. Las geometrías simplificadas se usan solo
para visualización. AccessConstraints=NONE no constituye una licencia expresa.
"""
from pathlib import Path
import argparse, csv, hashlib, json
import requests
from shapely.geometry import shape, mapping
import shapely

URL = 'https://sigudape.udape.gob.bo/geoserver/atlas2025/ows'
PARAMS = {'service':'WFS','version':'1.0.0','request':'GetFeature',
          'typeName':'atlas2025:pg_v_nbi_2024','outputFormat':'application/json','srsName':'EPSG:4326'}
SOURCE_SHA = '16f0e8ec7d39de34d3c44a79cf958aab22c45ccf28fede7f0b4fb7588980b1c9'

def prepare(output_dir, source_path=None, tolerance=0.0005, allow_source_change=False):
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    if source_path:
        raw=Path(source_path).read_bytes()
        source_url=requests.Request('GET',URL,params=PARAMS).prepare().url
    else:
        response=requests.get(URL,params=PARAMS,timeout=120);response.raise_for_status()
        raw=response.content;source_url=response.url
    digest=hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA and not allow_source_change:
        raise ValueError('La fuente cambió; verificar y registrar nueva versión antes de usar --allow-source-change.')
    data=json.loads(raw);features=data.get('features',[])
    if len(features)!=343:raise ValueError('La fuente no contiene las343unidades observadas; revisar cambio de cobertura.')
    codes=[f['properties']['codigo'] for f in features]
    if len(set(codes))!=343 or any(not isinstance(c,str) or len(c)!=6 or not c.isdigit() for c in codes):
        raise ValueError('Códigos municipales no únicos o sin seis dígitos.')
    geometries=[shape(f['geometry']) for f in features]
    if any(g.is_empty or not g.is_valid for g in geometries):
        raise ValueError('Geometría fuente vacía o inválida; no reparar silenciosamente.')
    simplified=[g.simplify(tolerance,preserve_topology=True) for g in geometries]
    if any(g.is_empty or not g.is_valid for g in simplified):
        raise ValueError('La simplificación produjo una geometría inválida.')
    derived=[];attributes=[]
    for feature,geom in zip(features,simplified):
        a=feature['properties']
        props={'codigo':a['codigo'],'departamento':a['departamen'],'provincia':a['provincia'],
               'municipio':a['municipio'],'municipio_o_tioc':a['mun_tioc'],'tipo_aioc':a['tioc_aioc'],
               'nbi2012_pct':a['f___nbi_12'],'nbi2024_pct':a['f___nbi_24'],'poblacion_censo2024':a['pobtotal']}
        if not (1 <= int(a['codigo'][:2]) <= 9):raise ValueError('Departamento fuera del catálogo1–9.')
        for key in ['nbi2012_pct','nbi2024_pct']:
            if props[key] is not None and not 0<=float(props[key])<=100:raise ValueError('NBI fuera de rango.')
        attributes.append(props)
        derived.append({'type':'Feature','id':a['codigo'],'properties':props,'geometry':mapping(geom)})
    raw_path=output/'udape_nbi2024_original.geojson';raw_path.write_bytes(raw)
    geo_path=output/'bolivia_municipios_udape_atlas2025_simplificado.geojson'
    geo_path.write_text(json.dumps({'type':'FeatureCollection','features':derived},ensure_ascii=False,separators=(',',':')))
    csv_path=output/'udape_municipios2024_atributos.csv'
    with csv_path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(attributes[0]));writer.writeheader();writer.writerows(attributes)
    areas=[abs(a.area-b.area)/a.area if a.area else 0 for a,b in zip(geometries,simplified)]
    report={
        'source_page':'https://sigudape.udape.gob.bo/atlas2025/',
        'institutional_explanation':'https://www.udape.gob.bo/colecciones',
        'service_url':source_url,'retrieval_date':'2026-11-15',
        'source_sha256':digest,'source_feature_count':len(features),'code_field':'codigo',
        'code_format':'Six-digit string with leading zero; departamento first two digits.',
        'reference_crs':'WGS84/EPSG4326, lon lat requested from WFS; bounds verified for Bolivia.',
        'bounds':shapely.total_bounds(geometries).tolist(),
        'source_invalid_geometries':0,'derived_invalid_geometries':0,
        'source_coverage_valid':bool(shapely.coverage_is_valid(geometries)),
        'simplification':{'method':'Shapely simplify, preserve_topology=True, applied to each municipal geometry',
                          'tolerance_degrees':tolerance,
                          'max_relative_planar_area_change':max(areas),
                          'area_change_is_diagnostic_not_substantive_measure':True,
                          'shared_boundaries_preserved_exactly':False,
                          'warning':'La capa original no constituye cobertura topológicamente perfecta; la simplificación conserva cada unidad, no garantiza coincidencia exacta de bordes entre unidades. Solo referencia visual; no usar para áreas, perímetros, deslindes ni asignación individual.'},
        'indicators_reference_year':2024,
        'geometry_vintage':'No explicit geometry year identified; published as municipal/TIOC layer in Atlas2025.',
        'attribution':'Unidad de Análisis de Políticas Sociales y Económicas (UDAPE), Atlas2025; indicadores NBI basados en Censos INE2012 y2024.',
        'license':{'explicit_reuse_license':None,'service_access_constraints':'NONE','service_fees':'NONE',
                   'site_footer':'Derechos Reservados | ©UDAPE2025',
                   'interpretation':'Acceso público al servicio verificado; no se afirma licencia abierta ni autorización irrestricta de redistribución.'},
        'derived_file_sha256':hashlib.sha256(geo_path.read_bytes()).hexdigest(),
        'derived_file_bytes':geo_path.stat().st_size,
        'csv_file_sha256':hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        'municipal_person_assignment':'None; no EHperson records used or linked.'}
    (output/'udape_municipal_geometry_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--source-path',type=Path);parser.add_argument('--tolerance',type=float,default=.0005)
    parser.add_argument('--allow-source-change',action='store_true');args=parser.parse_args()
    result=prepare(args.output_dir,args.source_path,args.tolerance,args.allow_source_change)
    print(json.dumps({'rows':result['source_feature_count'],'bytes':result['derived_file_bytes'],
                      'source_coverage_valid':result['source_coverage_valid']},ensure_ascii=False))
