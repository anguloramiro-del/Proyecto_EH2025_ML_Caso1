#!/usr/bin/env python3
"""Descarga y extrae agregados municipales oficiales INE Censo2024.

No usa personas EH ni desagrega estimaciones EH. No hace emparejamiento difuso.
Requiere openpyxl; requests solo al pasar --download. Géometría externa UDAPE
se usa exclusivamente para asignar códigos documentados, nunca valores EH.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,re,unicodedata
from pathlib import Path
from datetime import datetime,timezone
from openpyxl import load_workbook

SOURCES={
 '3020502_asistencia.xlsx':'https://nimbus.ine.gob.bo/index.php/s/o4WnYQoR38Zecyk/download',
 '3020504_promedio_estudio.xlsx':'https://nimbus.ine.gob.bo/index.php/s/p2wBM2H6oTajytF/download',
 '3110104_escolaridad_12_17.xlsx':'https://nimbus.ine.gob.bo/index.php/s/48tDmRnCCi8ponq/download',
 '3110107_agua.xlsx':'https://nimbus.ine.gob.bo/index.php/s/sw8xwg2X7XcR6L3/download',
 '3110108_saneamiento.xlsx':'https://nimbus.ine.gob.bo/index.php/s/ZntgBM4kdwG6Dg6/download',
 '3110109_electricidad.xlsx':'https://nimbus.ine.gob.bo/index.php/s/JHNWNoykMbZNWr5/download',
}
EDU='No incluye personas que residen habitualmente en el exterior y/o no declararon en la(s) pregunta(s).'
SERV='Población en viviendas particulares con personas presentes.'

def norm(x):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKD',x or '').encode('ascii','ignore').decode().casefold()).strip()
def key(r): return tuple(norm(x) for x in r[3:6])
def allrows(path):
    w=load_workbook(path,read_only=True,data_only=True)
    rows=list(w.active.iter_rows(values_only=True));w.close();return rows

def municipal_areas(rows, subcategory=False):
    """Return area/age rows indexed by exact municipality triple; preserve row IDs."""
    output={};area=None;last_key=None
    for rn,r in enumerate(rows,1):
        if len(r)<7 or r[2]!='Municipio/TIOC':continue
        k=key(r)
        if k!=last_key:area=None;last_key=k
        label=str(r[6]).strip() if r[6] is not None else ''
        if label==str(r[5]).strip():area='Total'
        elif label in ('Urbana','Rural'):area=label
        elif area is None:raise ValueError(('Área desconocida',rn,k,label))
        out=output.setdefault(k,{'geo':list(r[3:6])})
        # For hierarchical tables labels after area are ages or sanitation status.
        tag=area if label in (str(r[5]).strip(),'Urbana','Rural') else (area,label)
        if tag in out:raise ValueError(('Fila duplicada',rn,k,tag))
        out[tag]=(rn,r)
    return output

def write_csv(path, rows, fields=None):
    fields=fields or list(rows[0])
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

# Crosswalk exceptions audited against the source's own municipio and mun_tioc.
# No approximate string matching; codes refer only to UDAPE's matching geography.
ALIASES=[
 (['Beni','Territorio Indígena Multiétnico','TIOC-Territorio Indígena Multiétnico'],'080901','UDAPE provincia nula; municipio y mun_tioc identifican el TIOC TIM.'),
 (['Chuquisaca','Luis Calvo','Huacaya (Autonomía Guaraní Chaqueño de Huacaya)'],'011002','INE incluye nombre de autonomía; UDAPE mun_tioc=Huacaya.'),
 (['La Paz','General José Manuel Pando','Catacora'],'021902','UDAPE abrevia provincia como General Jose Manuel; mismo municipio.'),
 (['La Paz','General José Manuel Pando','Santiago de Machaca'],'021901','UDAPE abrevia provincia como General Jose Manuel; mismo municipio.'),
 (['Oruro','Ladislao Cabrera','Salinas de Garci Mendoza (Autonomía Indígena Originario Campesina de Salinas)'],'040801','INE incluye nombre de autonomía; mismo nombre base y jurisdicción.'),
 (['Oruro','Sabaya','Uru Chipaya (Nación Originaria Uru Chipaya)'],'040903','INE incluye nombre de nación; UDAPE mun_tioc=Uru Chipaya y municipio=Chipaya.'),
 (['Potosí','Nor Chichas','Vitichi'],'050602','UDAPE municipio=Vitichi; mun_tioc presenta variante Vitiche.'),
 (['Santa Cruz','Cordillera','Charagua (Autonomía Guaraní Charagua Iyambae)'],'070702','INE incluye nombre de autonomía; UDAPE municipio y mun_tioc=Charagua.'),
 (['Santa Cruz','Cordillera','Gutiérrez (Autonomía Indígena Kereimba Iyaambae)'],'070705','INE incluye nombre de autonomía; UDAPE mun_tioc=Gutiérrez.'),
]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--geojson',type=Path,required=True,help='GeoJSON municipal oficial UDAPE con343geometrías')
    p.add_argument('--download',action='store_true')
    a=p.parse_args();d=a.data_dir;d.mkdir(parents=True,exist_ok=True)
    if a.download:
        import requests
        for fn,url in SOURCES.items():
            response=requests.get(url,timeout=120);response.raise_for_status()
            if not response.content.startswith(b'PK'):raise ValueError('Respuesta no es XLSX: '+url)
            (d/fn).write_bytes(response.content)
    manifest=[]
    for fn,url in SOURCES.items():
        b=(d/fn).read_bytes()
        manifest.append({'filename':fn,'url':url,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    (d/'download_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    tables={fn:allrows(d/fn) for fn in SOURCES}
    parsed={fn:municipal_areas(rr) for fn,rr in tables.items()}
    base=parsed['3020502_asistencia.xlsx'];assert len(base)==343
    for fn,t in parsed.items(): assert set(t)==set(base),(fn,'Diferencia de cobertura')
    geo=json.loads(a.geojson.read_text(encoding='utf-8'))
    features=geo['features'];assert len(features)==343
    gprops=[dict(f['properties']) for f in features]
    # Admitir la capa derivada distribuida y la nomenclatura original del WFS.
    for gp in gprops:
        gp['departamen'] = gp.get('departamen', gp.get('departamento'))
        gp['mun_tioc'] = gp.get('mun_tioc', gp.get('municipio_o_tioc'))
    gcodes={str(x['codigo']).zfill(6):x for x in gprops};assert len(gcodes)==343
    gkeys={tuple(norm(x[k]) for k in ('departamen','provincia','mun_tioc')):str(x['codigo']).zfill(6) for x in gprops};assert len(gkeys)==343
    aliases={tuple(norm(y) for y in xs):(code,reason) for xs,code,reason in ALIASES}
    results=[];crosswalk=[];checks=[]
    for k,x in base.items():
        if k in gkeys: code=gkeys[k];method='triple_normalizado_exacto';reason='Mismos departamento, provincia y mun_tioc; normaliza mayúsculas, acentos y espacios.'
        elif k in aliases:code,reason=aliases[k];method='alias_explicito_auditado'
        else:raise ValueError(('Municipio sin equivalencia',x['geo']))
        gp=gcodes[code]
        crosswalk.append(dict(zip(['departamento_ine','provincia_ine','municipio_tioc_ine'],x['geo']))|{
           'codigo_municipio_udape':code,'departamento_udape':gp['departamen'],'provincia_udape':gp['provincia'],
           'municipio_udape':gp['municipio'],'mun_tioc_udape':gp['mun_tioc'],'metodo_union':method,'justificacion':reason})
        row=dict(zip(['departamento','provincia','municipio_tioc'],x['geo']))|{'codigo_municipio':code,'anio_censo':2024}
        er,ev=x[('Total','12 a 17')];ur,uv=x[('Urbana','12 a 17')];rr,rv=x[('Rural','12 a 17')]
        n=int(ev[19]);urban=uv[19];rural=rv[19]
        # A blank area population denotes no population only if the other area exactly exhausts total.
        if urban is None:assert rural==n;urban=0
        if rural is None:assert urban==n;rural=0
        assert urban+rural==n
        attended=n*ev[22]/100
        assert abs(attended-round(attended))<1e-6
        row.update({'poblacion_12_17_educacion':n,'poblacion_12_17_hombres':int(ev[20]),'poblacion_12_17_mujeres':int(ev[21]),
          'asistencia_12_17_pct':ev[22],'no_asistencia_12_17_pct':100-ev[22],
          'no_asistencia_12_17_n':n-round(attended),'asistencia_12_17_hombres_pct':ev[23],'asistencia_12_17_mujeres_pct':ev[24],
          'poblacion_12_17_urbana':urban,'poblacion_12_17_rural':rural,
          'ruralidad_12_17_pct':100*rural/n,'asistencia_12_17_urbana_pct':uv[22],'asistencia_12_17_rural_pct':rv[22],
          'fila_asistencia_ine':er})
        ar,av=parsed['3020504_promedio_estudio.xlsx'][k]['Total']
        row.update({'poblacion_19_mas_educacion':av[19],'anios_estudio_19_mas':av[22],
         'anios_estudio_19_mas_hombres':av[23],'anios_estudio_19_mas_mujeres':av[24],'fila_promedio_estudio_ine':ar})
        sr,sv=parsed['3110104_escolaridad_12_17.xlsx'][k]['Total']
        row.update({'poblacion_12_17_escolaridad':sv[19],'escolaridad_6_anios_12_17_pct':sv[31],
                    'fila_escolaridad_ine':sr})
        for filename,prefix in [('3110107_agua.xlsx','agua_mejorada'),('3110109_electricidad.xlsx','electricidad')]:
            fr,fv=parsed[filename][k]['Total']
            row.update({prefix+'_total_pct':fv[47],prefix+'_12_17_pct':fv[52],
                        'fila_'+prefix+'_ine':fr})
            if prefix=='agua_mejorada':
                row.update({'poblacion_viviendas_particulares':fv[29],
                            'poblacion_12_17_viviendas_particulares':fv[34]})
            else:
                assert fv[29]==row['poblacion_viviendas_particulares']
                assert fv[34]==row['poblacion_12_17_viviendas_particulares']
        zr,zv=parsed['3110108_saneamiento.xlsx'][k][('Total','Tiene')]
        ztot=parsed['3110108_saneamiento.xlsx'][k]['Total'][1]
        assert ztot[29]==row['poblacion_viviendas_particulares']
        row.update({'saneamiento_seguro_total_pct':zv[47],'saneamiento_seguro_12_17_pct':zv[52],
                    'fila_saneamiento_ine':zr})
        results.append(row)
    assert len({r['codigo_municipio'] for r in results})==343
    assert {r['codigo_municipio'] for r in results}==set(gcodes)
    results.sort(key=lambda r:r['codigo_municipio']);crosswalk.sort(key=lambda r:r['codigo_municipio_udape'])
    # National reconciliations independently read the published national rows.
    attendance_national=next(r for r in tables['3020502_asistencia.xlsx'] if len(r)>6 and r[2]=='País' and str(r[6]).strip()=='12 a 17')
    avnational=next(r for r in tables['3020504_promedio_estudio.xlsx'] if len(r)>6 and r[2]=='País' and r[6]=='Bolivia')
    schoolnational=next(r for r in tables['3110104_escolaridad_12_17.xlsx'] if len(r)>6 and r[2]=='País' and r[6]=='Bolivia')
    waternational=next(r for r in tables['3110107_agua.xlsx'] if len(r)>6 and r[2]=='País' and r[6]=='Bolivia')
    expected={'poblacion_12_17_educacion':attendance_national[19],'poblacion_19_mas_educacion':avnational[19],
             'poblacion_12_17_escolaridad':schoolnational[19],'poblacion_viviendas_particulares':waternational[29],
             'poblacion_12_17_viviendas_particulares':waternational[34]}
    for field,nat in expected.items():
        total=sum(r[field] for r in results);assert total==nat,(field,total,nat)
        checks.append({'control':field,'suma_municipal':total,'total_nacional_publicado':nat,'cumple':True})
    rate=100*(1-sum(r['no_asistencia_12_17_n'] for r in results)/expected['poblacion_12_17_educacion'])
    assert abs(rate-attendance_national[22])<1e-10
    checks.append({'control':'asistencia_12_17_pct','reconstruida':rate,'nacional_publicada':attendance_national[22],'cumple':True})
    for field in [c for c in results[0] if c.endswith('_pct')]:
        assert all(r[field] is None or isinstance(r[field],(float,int)) and math.isfinite(r[field]) and 0<=r[field]<=100 for r in results),field
    for field in ['asistencia_12_17_pct','ruralidad_12_17_pct','anios_estudio_19_mas','escolaridad_6_anios_12_17_pct',
                  'agua_mejorada_total_pct','electricidad_total_pct','saneamiento_seguro_total_pct']:
        assert all(r[field] is not None for r in results),(field,'Faltantes')
    write_csv(d/'municipios_censo2024_indicadores.csv',results)
    write_csv(d/'equivalencias_municipios_ine_udape.csv',crosswalk)
    (d/'aliases_municipales_auditados.json').write_text(json.dumps([{'geografia_ine':g,'codigo_udape':c,'justificacion':j} for g,c,j in ALIASES],indent=2,ensure_ascii=False)+'\n')
    report={'anio':2024,'unidad':'municipio/TIOC','filas':len(results),'duplicados_codigo':0,
       'union_exacta_normalizada':sum(r['metodo_union']=='triple_normalizado_exacto' for r in crosswalk),
       'union_alias_explicito':sum(r['metodo_union']=='alias_explicito_auditado' for r in crosswalk),
       'sin_union':0,'valores_imputados':0,'controles_nacionales':checks,
       'no_asistencia_12_17_n_nacional':sum(r['no_asistencia_12_17_n'] for r in results),
       'faltantes_por_columna':{c:sum(r[c] is None for r in results) for c in results[0]},
       'advertencia':'No se vinculan individuos EH2025 con estos municipios. No asistencia censal no demuestra abandono longitudinal. Los denominadores de asistencia, escolaridad y servicios no son intercambiables.'}
    (d/'validacion_municipios_censo2024.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    definitions={}
    def add(cols,definition,unit,universe,source,sourcecols):
        for col in cols.split(','):definitions[col]={'columna':col,'definicion':definition,'unidad':unit,'anio':2024,'universo':universe,'fuente_archivo':source,'columnas_excel_2024':sourcecols}
    add('departamento,provincia,municipio_tioc','Nombres oficiales conservados del cuadro INE.','texto','Geografía municipal/TIOC INE','3020502_asistencia.xlsx','D,E,F')
    add('codigo_municipio','Código6dígitos como texto, unido solo por geografía con crosswalk auditado.','código texto','Cartografía municipal/TIOC UDAPE Atlas2025','udape_nbi2024.geojson','codigo')
    add('anio_censo','Año de los indicadores censales.','año','Censo2024','todos','2024')
    add('poblacion_12_17_educacion,poblacion_12_17_hombres,poblacion_12_17_mujeres','Población12–17 incluida en indicador de asistencia; total y por sexo respectivamente.','personas','12–17. '+EDU,'3020502_asistencia.xlsx','T,U,V')
    add('asistencia_12_17_pct,asistencia_12_17_hombres_pct,asistencia_12_17_mujeres_pct','Tasa de asistencia educativa12–17; total, hombres y mujeres respectivamente.','porcentaje0–100','12–17. '+EDU,'3020502_asistencia.xlsx','W,X,Y')
    add('no_asistencia_12_17_pct','100 menos tasa de asistencia; no es abandono longitudinal.','porcentaje0–100','12–17. '+EDU,'3020502_asistencia.xlsx','derivado100-W')
    add('no_asistencia_12_17_n','Población válida por(100−tasa)/100; entero reconstruido y verificado contra precisión del cuadro.','personas','12–17. '+EDU,'3020502_asistencia.xlsx','derivadoT*(100-W)/100')
    add('poblacion_12_17_urbana,poblacion_12_17_rural','Población12–17 urbana/rural del mismo cuadro de asistencia. Si área no existente se registra0 solo verificando que el área complementaria agota total.','personas','12–17. '+EDU,'3020502_asistencia.xlsx','T:bloquesUrbana/Rural12a17')
    add('ruralidad_12_17_pct','100*poblacion_12_17_rural/poblacion_12_17_educacion.','porcentaje0–100','12–17. '+EDU,'3020502_asistencia.xlsx','derivadoT:Rural/Total12a17')
    add('asistencia_12_17_urbana_pct,asistencia_12_17_rural_pct','Tasa asistencia12–17 por área; vacía cuando no existe población del área, sin reemplazar tasa por0.','porcentaje0–100','12–17 porárea. '+EDU,'3020502_asistencia.xlsx','W:bloquesUrbana/Rural12a17')
    add('poblacion_19_mas_educacion','Población19+del indicador años promedio de estudio.','personas','19+. '+EDU,'3020504_promedio_estudio.xlsx','T:total')
    add('anios_estudio_19_mas,anios_estudio_19_mas_hombres,anios_estudio_19_mas_mujeres','Años promedio de estudio19+; total, hombres y mujeres respectivamente. Indicador contextual agregado, no atributo de adolescentes EH.','años','19+. '+EDU,'3020504_promedio_estudio.xlsx','W,X,Y:total')
    add('poblacion_12_17_escolaridad','Población12–17 del indicador escolaridad>=6años. Puede diferir del denominador de asistencia por declaración de respuestas.','personas','12–17. '+EDU,'3110104_escolaridad_12_17.xlsx','T')
    add('escolaridad_6_anios_12_17_pct','Porcentaje12–17 que completó al menos6años de escolaridad.','porcentaje0–100','12–17. '+EDU,'3110104_escolaridad_12_17.xlsx','AF(32)')
    add('poblacion_viviendas_particulares,poblacion_12_17_viviendas_particulares','Población total y12–17 respectivamente en viviendas particulares; denominador de servicios.','personas',SERV,'3110107_agua.xlsx','AD(30),AI(35)')
    for prefix,fn,defn in [('agua_mejorada','3110107_agua.xlsx','Acceso a fuente mejorada de agua'),('electricidad','3110109_electricidad.xlsx','Acceso a electricidad'),('saneamiento_seguro','3110108_saneamiento.xlsx','Acceso a servicio de saneamiento gestionado de manera segura; categoríaTiene, excluyeTiene limitado')]:
        add(prefix+'_total_pct,'+prefix+'_12_17_pct',defn+'; población total y12–17 respectivamente.','porcentaje0–100',SERV,fn,'AV(48),BA(53)'+(';categoríaTieneenáreaTotal' if prefix=='saneamiento_seguro' else ''))
    for col,fn in [('fila_asistencia_ine','3020502_asistencia.xlsx'),('fila_promedio_estudio_ine','3020504_promedio_estudio.xlsx'),('fila_escolaridad_ine','3110104_escolaridad_12_17.xlsx'),('fila_agua_mejorada_ine','3110107_agua.xlsx'),('fila_electricidad_ine','3110109_electricidad.xlsx'),('fila_saneamiento_ine','3110108_saneamiento.xlsx')]:
        add(col,'Número de fila Excel de la observación original; trazabilidad sin alterar fuente.','fila1based','Metadato',fn,'fila')
    assert set(definitions)==set(results[0]),(set(results[0])-set(definitions),set(definitions)-set(results[0]))
    write_csv(d/'diccionario_municipios_censo2024.csv',list(definitions.values()))
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
