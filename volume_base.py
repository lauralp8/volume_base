#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NetApp ONTAP SVM Creation and Configuration Script

This script automates the creation and configuration of Storage Virtual Machines (SVMs)
on NetApp ONTAP systems using the NetApp ONTAP REST API Python Client Library.

Features:
    - SVM creation with custom parameters
    - FCP service configuration
    - Multiple network interfaces (FCP LIFs)
    - Management interface creation
    - Protocol configuration
    - Comprehensive error handling and validation

Requirements:
    - NetApp ONTAP 9.6+
    - Python 3.7+
    - netapp-ontap library
    - PyYAML library

Author: NetApp ONTAP Automation
Version: 1.0.0
"""

# ============================================================================
# IMPORTS
# ============================================================================
from netapp_ontap import config, HostConnection, NetAppRestError
from netapp_ontap.resources import Cluster, EmsEvent, Volume
import yaml
import json
import os
from datetime import datetime


# ============================================================================
# SCRIPT INITIALIZATION
# ============================================================================
print("\n" + "="*70)
print("  NetApp ONTAP FCP SVM Creation Script")
print("  Using NetApp ONTAP Python Client Library")
print("="*70)
print("\n[*] Initializing SVM creation workflow...")


# ============================================================================
# YAML CONFIGURATION FUNCTION
# ============================================================================

def config_loader(path="config.yaml"):
    """
    Carga la configuración desde un archivo YAML con validación completa
    
    Lee el archivo de configuración y valida que contenga las secciones
    necesarias para crear una SVM en NetApp ONTAP.
    
    Args:
        path: Ruta al archivo de configuración (por defecto 'config.yaml')
    
    Returns:
        dict: Diccionario con la configuración cargada, o None si falla
    """
    try:
        print(f"[+] Config.yaml loader: {path}")
        
        # Abrir y leer el contenido del archivo YAML
        with open(path, 'r', encoding='utf-8') as file:
            config_data = yaml.safe_load(file)
        
        # VALIDACIONES
        # Validar que el archivo no esté vacío
        if config_data is None:
            print(f"[ERROR] File '{path}' is empty or doen't contain valid YAML")
            return None
        
        # Validar estructura: debe contener seccion 'cluster'
        if 'cluster' not in config_data:
            print(f"[ERROR]Incomplete configuration: missing 'cluster' section")
            return None
        
        # Validar estructura: debe contener seccion 'svm'
        if 'svm' not in config_data:
            print(f"[ERROR] Incomplete configuration: missing 'svm' section")
            return None
        
        print(f"[+] Configuration loaded successfully")

        # Mostrar resumen de la configuración cargada
        print(f"[+] Target cluster: {config_data['cluster'].get('host', 'N/A')}")
        print(f"[+] SVM to create: {config_data['svm'].get('name', 'N/A')}")
        
        return config_data
    
    # CONTROL DE ERRORES
    except FileNotFoundError:
        print(f"[ERROR] File not found: {path}")
        print(f"[ERROR] Please check the path and try again")
        return None
    
    except yaml.YAMLError as e:
        print(f"[ERROR] Invalid YAML format in '{path}'")
        print(f"[ERROR] Detail: {str(e)}")
        return None
    
    except PermissionError:
        print(f"[ERROR] Insufficient permissions to read: {path}")
        return None
    
    except Exception as e:
        print(f"[ERROR] Unexpected failure: {type(e).__name__}")
        print(f"[ERROR] Message: {str(e)}")
        return None


# ============================================================================
# SAVE TO LOG FUNCTION
# ============================================================================

def save_to_log(operation_name, data):
    """
    Guarda datos en un archivo JSON dentro de la carpeta logs/ con timestamp
    
    Args:
        operation_name (str): Nombre de la operación (ej: 'create_svm', 'fcp_create')
        data (dict): Datos a guardar (normalmente el show de la cabina)
    
    Returns:
        str: Ruta del archivo creado
    
    Ejemplo:
        save_to_log('create_svm', svm_data)
        # Crea: logs/create_svm_20260129_143025.json
    """
    try:
        # Crear carpeta logs si no existe
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        # Generar timestamp: YYYYMMDD_HHMMSS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Nombre del archivo: operation_YYYYMMDD_HHMMSS.json
        filename = f"{logs_dir}/{operation_name}_{timestamp}.json"
        
        # Guardar en formato JSON
        with open(filename, 'w', encoding='utf-8') as log_file:
            json.dump(data, log_file, indent=2, ensure_ascii=False)
        
        print(f"[LOG] Saved to: {filename}")
        return filename
    
    except Exception as e:
        print(f"[WARNING] Could not save log: {str(e)}")
        return None


# ============================================================================
# CLUSTER CONNECTION FUNCTION
# ============================================================================

def cluster_connection(cluster_config):
    """
    Establece conexión con la cabina NetApp ONTAP y verifica acceso
    
    Conecta con el cluster usando las credenciales proporcionadas y realiza
    una consulta de prueba para validar que el acceso es correcto.
    
    Args:
        cluster_config: Diccionario con claves 'host', 'username', 'password'
    
    Returns:
        bool: True si conexión exitosa, False si hay errores
    """
    try:
        print(f"\n[*] Establishing connection to cluster: {cluster_config.get('host', 'N/A')}")
        
        # Validar que existan todos los campos necesarios
        required_keys = ['host', 'username', 'password']
        # Itera por cada clave requerida y guarda en una lista las que faltan
        missing_keys = [key for key in required_keys if key not in cluster_config]
        
        if missing_keys:
            print(f"[ERROR] Missing required fields in cluster config: {', '.join(missing_keys)}")
            return False
        
        # Establecer conexión con la cabina
        config.CONNECTION = HostConnection(
            cluster_config['host'],
            username=cluster_config['username'],
            password=cluster_config['password'],
            verify=False 
        )
        
        # Verificar acceso haciendo una consulta al cluster
        cluster_info = Cluster()
        cluster_info.get()
        
        print(f"[+] Connection successful!")
        print(f"[+] Cluster name: {cluster_info.name}")
        print(f"[+] ONTAP version: {cluster_info.version.full}")

        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp REST API error")
        print(f"[ERROR] HTTP status: {error.status_code}")
        
        # Detallar el tipo de error según el código HTTP
        if error.status_code == 401:
            print(f"[ERROR] Authentication failed")
            print(f"[ERROR] Invalid username or password for user '{cluster_config.get('username')}'")
        elif error.status_code == 403:
            print(f"[ERROR] Forbidden - User lacks required permissions")
        elif error.status_code == 404:
            print(f"[ERROR] Resource not found - Check cluster URL")
        else:
            print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
        
        return False
    
    except KeyError as e:
        print(f"[ERROR] Configuration error - Missing key: {str(e)}")
        return False
    
    except ConnectionError:
        print(f"[ERROR] Cannot reach host '{cluster_config.get('host')}'")
        print(f"[ERROR] Check network connectivity and hostname/IP")
        return False
    
    except TimeoutError:
        print(f"[ERROR] Connection timeout to '{cluster_config.get('host')}'")
        print(f"[ERROR] Cluster is not responding")
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error: {type(e).__name__}")
        print(f"[ERROR] Message: {str(e)}")
        return False


# ============================================================================
# VOLUME MANAGEMENT FUNCTIONS
# ============================================================================

def volume_create(volume_config):
    """
    Crea un volumen en la cabina NetApp ONTAP usando la REST API
    
    Basado en el comando:
    volume create -vserver vservername -volume volumename -aggregate aggrname 
                  -size size -security-style style -junction-path path -policy policy
    
    Args:
        volume_config: Diccionario con las configuraciones del volumen desde config.yaml
                      Debe contener: vserver, name, aggregate, size, security_style,
                      junction_path, export_policy
    
    Returns:
        bool: True si el volumen se creó exitosamente, False en caso contrario
    """
    try:
        print(f"\n[*] Starting volume creation process...")
        print(f"[*] Volume name: {volume_config.get('name', 'N/A')}")
        print(f"[*] Vserver: {volume_config.get('vserver', 'N/A')}")
        
        # Validar campos requeridos
        required_keys = ['name', 'vserver', 'aggregate', 'size', 'security_style', 
                        'junction_path', 'export_policy']
        missing_keys = [key for key in required_keys if key not in volume_config]
        
        if missing_keys:
            print(f"[ERROR] Missing required fields in volume config: {', '.join(missing_keys)}")
            return False
        
        # Crear el objeto Volume
        print(f"\n[*] Creating volume resource object...")
        volume = Volume()
        
        # Configurar propiedades del volumen según config.yaml
        volume.name = volume_config['name']
        volume.svm = {"name": volume_config['vserver']}
        volume.aggregates = [{"name": volume_config['aggregate']}]
        volume.size = volume_config['size']
        
        # Configurar NAS properties (security style, junction path, export policy)
        volume.nas = {
            "security_style": volume_config['security_style'],
            "path": volume_config['junction_path'],
            "export_policy": {"name": volume_config['export_policy']}
        }
        
        print(f"[*] Volume configuration:")
        print(f"    - Name: {volume.name}")
        print(f"    - SVM: {volume_config['vserver']}")
        print(f"    - Aggregate: {volume_config['aggregate']}")
        print(f"    - Size: {volume_config['size']}")
        print(f"    - Security Style: {volume_config['security_style']}")
        print(f"    - Junction Path: {volume_config['junction_path']}")
        print(f"    - Export Policy: {volume_config['export_policy']}")
        
        # POST: Crear el volumen en la cabina
        print(f"\n[*] Sending POST request to create volume...")
        volume.post(hydrate=True)
        
        print(f"[+] Volume '{volume.name}' created successfully!")
        print(f"[+] Volume UUID: {volume.uuid}")
        
        # GET: Obtener todos los detalles del volumen creado
        print(f"\n[*] Retrieving volume details from storage array...")
        
        # Obtener la información completa del volumen recién creado
        created_volume = Volume(uuid=volume.uuid)
        created_volume.get()
        
        # Preparar datos para el log
        volume_data = {
            'operation': 'volume_create',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'volume_info': {
                'uuid': created_volume.uuid,
                'name': created_volume.name,
                'svm': created_volume.svm.name if hasattr(created_volume, 'svm') and created_volume.svm else 'N/A',
                'size': str(created_volume.size) if hasattr(created_volume, 'size') else 'N/A',
                'state': created_volume.state if hasattr(created_volume, 'state') else 'N/A',
                'style': created_volume.style if hasattr(created_volume, 'style') else 'N/A',
                'type': created_volume.type if hasattr(created_volume, 'type') else 'N/A',
                'aggregates': [aggr.name for aggr in created_volume.aggregates] if hasattr(created_volume, 'aggregates') and created_volume.aggregates else [],
                'nas': {
                    'security_style': created_volume.nas.security_style if hasattr(created_volume, 'nas') and hasattr(created_volume.nas, 'security_style') else 'N/A',
                    'path': created_volume.nas.path if hasattr(created_volume, 'nas') and hasattr(created_volume.nas, 'path') else 'N/A',
                    'export_policy': created_volume.nas.export_policy.name if hasattr(created_volume, 'nas') and hasattr(created_volume.nas, 'export_policy') and created_volume.nas.export_policy else 'N/A'
                },
                'create_time': str(created_volume.create_time) if hasattr(created_volume, 'create_time') else 'N/A'
            },
            'input_config': volume_config
        }
        
        # SHOW: Mostrar información como "volume show"
        print(f"\n{'='*80}")
        print(f"  Volume Show - {created_volume.name}")
        print(f"{'='*80}")
        print(f"Volume Name:        {volume_data['volume_info']['name']}")
        print(f"Volume UUID:        {volume_data['volume_info']['uuid']}")
        print(f"Vserver:            {volume_data['volume_info']['svm']}")
        print(f"Aggregate:          {', '.join(volume_data['volume_info']['aggregates'])}")
        print(f"Size:               {volume_data['volume_info']['size']}")
        print(f"State:              {volume_data['volume_info']['state']}")
        print(f"Style:              {volume_data['volume_info']['style']}")
        print(f"Type:               {volume_data['volume_info']['type']}")
        print(f"Security Style:     {volume_data['volume_info']['nas']['security_style']}")
        print(f"Junction Path:      {volume_data['volume_info']['nas']['path']}")
        print(f"Export Policy:      {volume_data['volume_info']['nas']['export_policy']}")
        print(f"Created:            {volume_data['volume_info']['create_time']}")
        print(f"{'='*80}\n")
        
        # Guardar en log usando save_to_log
        save_to_log('volume_create', volume_data)
        
        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp API error during volume creation")
        print(f"[ERROR] HTTP Status: {error.status_code}")
        if error.http_err_response and error.http_err_response.http_response:
            print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
        else:
            print(f"[ERROR] Details: {str(error)}")
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error during volume creation: {type(e).__name__}")
        print(f"[ERROR] Details: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# EVENT LOG RETRIEVAL FUNCTION
# ============================================================================

def get_event_logs(max_records=100):
    """
    Obtiene los logs de eventos del sistema NetApp ONTAP
    
    Args:
        max_records: Número máximo de eventos a recuperar (default: 100)
    
    Returns:
        bool: True si se obtuvieron exitosamente, False si hubo error
    """
    try:
        print(f"\n[*] Retrieving event logs from cluster...")
        
        # GET: Obtener eventos del sistema desde la cabina
        events_list = []
        ems_events = EmsEvent.get_collection(max_records=max_records)
        
        for event in ems_events:
            event_data = {
                'index': event.index if hasattr(event, 'index') else 'N/A',
                'time': str(event.time) if hasattr(event, 'time') else 'N/A',
                'node': event.node.name if hasattr(event, 'node') and event.node else 'N/A',
                'severity': event.message.severity if hasattr(event, 'message') and hasattr(event.message, 'severity') else 'N/A',
                'event': event.message.name if hasattr(event, 'message') and hasattr(event.message, 'name') else 'N/A'
            }
            events_list.append(event_data)
        
        event_log_data = {
            'total_events': len(events_list),
            'max_records_requested': max_records,
            'events': events_list
        }
        
        # SHOW: Mostrar información como "event log show"
        print(f"\n{'='*110}")
        print(f"  Event Log Show")
        print(f"{'='*110}")
        print(f"{'Index':<8} {'Time':<25} {'Node':<20} {'Severity':<12} {'Event':<40}")
        print(f"{'-'*8} {'-'*25} {'-'*20} {'-'*12} {'-'*40}")
        
        for evt in events_list[:20]:  # Mostrar solo los primeros 20 en pantalla
            print(f"{str(evt['index']):<8} {evt['time']:<25} {evt['node']:<20} {evt['severity']:<12} {evt['event']:<40}")
        
        if len(events_list) > 20:
            print(f"... ({len(events_list) - 20} more events)")
        
        print(f"\nTotal events retrieved: {len(events_list)}")
        print(f"{'='*110}\n")
        
        # Guardar en log con timestamp
        save_to_log('event_logs', event_log_data)
        
        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp API error during event log retrieval")
        print(f"[ERROR] HTTP Status: {error.status_code}")
        if error.http_err_response and error.http_err_response.http_response:
            print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
        else:
            print(f"[ERROR] Details: {str(error)}")
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error during event log retrieval: {type(e).__name__}")
        print(f"[ERROR] Details: {str(e)}")
        return False

# ============================================================================
# CALLING WORKFLOW
# ============================================================================

# CONFIG YAML LOADER
# Cargar la configuración desde el archivo YAML
config_data = config_loader()

# Verificar que la configuración se cargó exitosamente
if config_data is None:
    print("\n[ERROR] Cannot continue without valid configuration")
    print("[ERROR] Check the config.yaml file and try again")
    exit(1)
else:
    print("\n[SUCCESS] Configuration loaded - Proceeding with pre-checks")

# CLUSTER CONNECTION CHECK
# Establecer conexión y verificar acceso a la cabina NetApp
if not cluster_connection(config_data['cluster']):
    print("\n[ERROR] Failed to connect to NetApp cluster")
    print("[ERROR] Fix connection issues before continuing")
    exit(1)

print("\n[+] All pre-checks passed - Ready to create SVM")

# VOLUME CREATION STEPS
# Crear volumen usando la configuración del archivo YAML
print("\n" + "="*80)
print("  STARTING VOLUME CREATION WORKFLOW")
print("="*80)

if volume_create(config_data['volume']):
    print("\n[SUCCESS] Volume creation completed successfully!")
else:
    print("\n[ERROR] Volume creation failed")
    print("[ERROR] Check the error messages above for details")
    exit(1)


# Obtener event logs de la cabina como backup
if get_event_logs(max_records=100):
    print("\n[SUCCESS] Event logs backup completed!")
else:
    print("\n[WARNING] Event logs backup failed (non-critical)")
