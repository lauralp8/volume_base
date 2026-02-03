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
from netapp_ontap.resources import Cluster, Svm, FcpService, FcInterface, IpInterface, EmsEvent
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
# SVM MANAGEMENT FUNCTIONS
# ============================================================================

def create_svm(svm_config):
    """
    Crea una SVM en NetApp ONTAP con los parámetros del config.yaml
    
    Args:
        svm_config: Diccionario con la configuración de la SVM desde config.yaml
    
    Returns:
        bool: True si se creó exitosamente, False si hubo error
    """
    try:
        # Extraer parámetros del config.yaml
        svm_name = svm_config.get('name')
        ipspace = svm_config.get('ipspace')
        language = svm_config.get('language')
        security_style = svm_config.get('security_style')
        aggregate = svm_config.get('aggregate')
        
        # VALIDACIONES
        # Validar que exista el valor obligatorio 'name'
        if not svm_name:
            print(f"[ERROR] 'name' is required in svm configuration")
            return False
        
        print(f"\n[*] Creating SVM: {svm_name}")
        
        # Verificar si la SVM ya existe
        print(f"[*] Checking if SVM already exists...")
        existing_svm = Svm.find(name=svm_name)
        if existing_svm:
            print(f"[ERROR] SVM '{svm_name}' already exists on the cluster")
            return False
        
        # SVM
        # Crear objeto SVM
        new_svm = Svm()
        new_svm.name = svm_name
        
        # DATOS ENVIADOS AL CLÚSTER DESDE EL CONFIG.YAML
        # Configurar IPspace 
        if ipspace:
            new_svm.ipspace = {'name': ipspace}
            print(f"[*] IPspace: {ipspace}")
        
        # Configurar idioma
        if language:
            new_svm.language = language
            print(f"[*] Language: {language}")
        
        # Configurar security style
        if security_style:
            new_svm.security_style = security_style
            print(f"[*] Security Style: {security_style}")
        
        # Especificar el agregado para el volumen raíz
        new_svm.aggregates = [{'name': aggregate}]
        print(f"[*] Aggregate: {aggregate}")
        
        # Enviar petición de creación al cluster
        print(f"[*] Sending creation request...")
        new_svm.post()
        
        print(f"[+] SVM '{svm_name}' created successfully!")
        
        # SHOW - Obtener y mostrar datos reales de la cabina
        print(f"\n[*] Retrieving SVM details from cluster...")
        svm_created = Svm.find(name=svm_name)
        svm_show = Svm(uuid=svm_created.uuid)
        svm_show.get()
        
        # Preparar datos para guardar en log
        svm_data = {
            'uuid': svm_show.uuid,
            'name': svm_show.name,
            'state': svm_show.state if hasattr(svm_show, 'state') else None,
            'ipspace': svm_show.ipspace.name if hasattr(svm_show, 'ipspace') and svm_show.ipspace else None,
            'language': svm_show.language if hasattr(svm_show, 'language') else None,
            'security_style': svm_show.security_style if hasattr(svm_show, 'security_style') else None,
            'aggregates': [
                {'name': aggr.name, 'uuid': aggr.uuid} 
                for aggr in svm_show.aggregates
            ] if hasattr(svm_show, 'aggregates') and svm_show.aggregates else []
        }
        
        # Imprimir show de la SVM
        print(f"\n{'='*60}")
        print(f"  SVM SHOW - Data from NetApp Cluster")
        print(f"{'='*60}")
        print(f"UUID:                    {svm_data['uuid']}")
        print(f"Name:                    {svm_data['name']}")
        print(f"State:                   {svm_data['state'] or 'N/A'}")
        print(f"IPspace:                 {svm_data['ipspace'] or 'N/A'}")
        print(f"Language:                {svm_data['language'] or 'N/A'}")
        print(f"Security Style:          {svm_data['security_style'] or 'N/A'}")
        if svm_data['aggregates']:
            print(f"Aggregates:")
            for aggr in svm_data['aggregates']:
                print(f"  - {aggr['name']} (UUID: {aggr['uuid']})")
        print(f"{'='*60}\n")
        
        # Guardar en log con timestamp
        save_to_log('create_svm', svm_data)
        
        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp API error during SVM creation")
        print(f"[ERROR] HTTP Status: {error.status_code}")
        
        # Proporcionar información detallada según el error
        if error.status_code == 409:
            print(f"[ERROR] Conflict - SVM may already exist or name is in use")
        elif error.status_code == 400:
            print(f"[ERROR] Bad request - Invalid parameters")
            print(f"[ERROR] Common causes:")
            print(f"[ERROR] - Aggregate 'aggr1' doesn't exist (check aggregate name)")
            print(f"[ERROR] - Invalid ipspace name")
            print(f"[ERROR] - Invalid language code")
            print(f"[ERROR] Response: {error.http_err_response.http_response.text}")
        else:
            print(f"[ERROR] Response: {error.http_err_response.http_response.text}")
        
        return False
    
    except KeyError as e:
        print(f"[ERROR] Missing required configuration key: {str(e)}")
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error during SVM creation: {type(e).__name__}")
        print(f"[ERROR] Details: {str(e)}")
        return False


def modify_svm(svm_config):
    """
    Modifica una SVM configurando parámetros de espacio lógico
    
    Args:
        svm_config: Diccionario con la configuración de la SVM del config.yaml
    
    Returns:
        bool: True si se modificó exitosamente, False si hubo error
    """
    try:
        # Extraer nombre de la SVM del config
        svm_name = svm_config.get('name')
        
        # Extraer lista de agregados del config.yaml
        aggr_list = svm_config.get('aggr_list', [])

        # Extraer valores de espacio lógico del config.yaml
        space_reporting = svm_config.get('is_space_reporting_logical', False)
        space_enforcement = svm_config.get('is_space_enforcement_logical', False)
        
        
        print(f"\n[*] Modifying SVM: {svm_name}")
        
        # Buscar la SVM
        svm = Svm.find(name=svm_name)
        if not svm:
            print(f"[ERROR] SVM '{svm_name}' not found")
            return False
        
        # Configurar lista de agregados desde config.yaml
        if aggr_list:
            svm.aggregates = [{'name': aggr} for aggr in aggr_list]
            print(f"[*] Aggregate list: {', '.join(aggr_list)}")
        
        # Configurar parámetros de espacio lógico desde config.yaml
        svm.is_space_reporting_logical = space_reporting
        svm.is_space_enforcement_logical = space_enforcement
        
        print(f"[*] is_space_reporting_logical: {space_reporting}")
        print(f"[*] is_space_enforcement_logical: {space_enforcement}")
        
        # Aplicar cambios
        print(f"[*] Applying changes...")
        svm.patch()
        
        print(f"[+] SVM '{svm_name}' modified successfully!")
        
        # GET: Obtener datos reales de la SVM desde la cabina
        print(f"[*] Retrieving SVM details from cluster...")
        svm_updated = Svm.find(name=svm_name)
        if svm_updated:
            svm_updated.get(fields='aggregates,is_space_reporting_logical,is_space_enforcement_logical')
            
            # Extraer lista de agregados
            aggr_list_data = []
            if hasattr(svm_updated, 'aggregates') and svm_updated.aggregates:
                aggr_list_data = [{'name': aggr.name, 'uuid': aggr.uuid} for aggr in svm_updated.aggregates]
            
            # Extraer los datos para el show
            svm_data = {
                'vserver_name': svm_name,
                'aggr_list': aggr_list_data,
                'is_space_reporting_logical': svm_updated.is_space_reporting_logical if hasattr(svm_updated, 'is_space_reporting_logical') else False,
                'is_space_enforcement_logical': svm_updated.is_space_enforcement_logical if hasattr(svm_updated, 'is_space_enforcement_logical') else False
            }
            
            # SHOW: Mostrar información de la SVM modificada
            print(f"\n{'='*60}")
            print(f"  SVM Modification Show")
            print(f"{'='*60}")
            print(f"                 Vserver Name: {svm_data['vserver_name']}")
            print(f"is-space-reporting-logical: {svm_data['is_space_reporting_logical']}")
            print(f"is-space-enforcement-logical: {svm_data['is_space_enforcement_logical']}")
            print(f"                   Aggr List:")
            if svm_data['aggr_list']:
                for aggr in svm_data['aggr_list']:
                    print(f"  - {aggr['name']}")
            else:
                print(f"  (No aggregates configured)")
            print(f"{'='*60}\n")
            
            # Guardar en log con timestamp
            save_to_log('modify_svm', svm_data)
        else:
            print(f"[WARNING] Could not retrieve SVM details")
        
        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp API error")
        print(f"[ERROR] HTTP Status: {error.status_code}")
        print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error: {type(e).__name__}")
        print(f"[ERROR] Details: {str(e)}")
        return False


# ============================================================================
# FCP PROTOCOL CONFIGURATION FUNCTIONS
# ============================================================================

def fcp_create(svm_config):
    """
    Crea un servicio FCP en la SVM y lo configura con status-admin desde config.yaml
    
    Args:
        svm_config: Diccionario con la configuración de la SVM del config.yaml
    
    Returns:
        bool: True si se creó exitosamente, False si hubo error
    """
    try:
        # Extraer nombre de la SVM del config
        svm_name = svm_config.get('name')
        
        # Extraer status_admin del config.yaml (viene como "up" o "down")
        fcp_status_admin_value = svm_config.get('fcp_status_admin', 'down')
        
        # Convertir "up"/"down" a True/False
        if fcp_status_admin_value == 'up':
            fcp_status_admin = True
        else:
            fcp_status_admin = False
        
        print(f"\n[*] Creating FCP service on SVM: {svm_name}")
        
        # Crear objeto FCP service
        fcp = FcpService()
        fcp.svm = {'name': svm_name}
        fcp.enabled = fcp_status_admin
        
        # Crear el servicio FCP
        print(f"[*] Creating FCP service...")
        fcp.post()
        
        print(f"[+] FCP service created successfully!")
        
        # GET: Obtener datos reales del servicio FCP desde la cabina
        print(f"[*] Retrieving FCP service details from cluster...")
        fcp_service = FcpService.find(svm={'name': svm_name})
        if fcp_service:
            fcp_service.get()
            
            # Extraer los datos para el show
            fcp_data = {
                'vserver_name': svm_name,
                'target_name': fcp_service.target.name if hasattr(fcp_service, 'target') and fcp_service.target else 'N/A',
                'administrative_status': 'up' if fcp_service.enabled else 'down',
                'svm_uuid': fcp_service.svm.uuid if hasattr(fcp_service.svm, 'uuid') else 'N/A'
            }
            
            # SHOW: Mostrar información como "vserver fcp show -vserver <name>"
            print(f"\n{'='*60}")
            print(f"  FCP Service Show")
            print(f"{'='*60}")
            print(f"         Vserver Name: {fcp_data['vserver_name']}")
            print(f"          Target Name: {fcp_data['target_name']}")
            print(f"Administrative Status: {fcp_data['administrative_status']}")
            print(f"{'='*60}\n")
            
            # Guardar en log con timestamp
            save_to_log('fcp_create', fcp_data)
        else:
            print(f"[WARNING] Could not retrieve FCP service details")
        
        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp API error during FCP creation")
        print(f"[ERROR] HTTP Status: {error.status_code}")
        
        if error.status_code == 409:
            print(f"[ERROR] FCP service may already exist on this SVM")
        elif error.status_code == 400:
            print(f"[ERROR] Bad request - Invalid parameters")
        else:
            print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
        
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error during FCP creation: {type(e).__name__}")
        print(f"[ERROR] Details: {str(e)}")
        return False


def configure_protocols(svm_config):
    """
    Configura los protocolos permitidos en la SVM (allowed=true/false)
    
    Args:
        svm_config: Diccionario con la configuración de la SVM del config.yaml
                    Debe incluir la sección 'protocols' con cada protocolo y su valor
    
    Returns:
        bool: True si se configuró exitosamente, False si hubo error
    """
    try:
        # Extraer nombre de la SVM del config
        svm_name = svm_config.get('name')
        
        # Extraer diccionario de protocolos del config.yaml
        protocols_config = svm_config.get('protocols', {})
        
        # Validar que haya protocolos para configurar
        if not protocols_config:
            print(f"[WARNING] No protocol configuration found in config.yaml")
            return True
        
        print(f"\n[*] Configuring protocols for SVM: {svm_name}")
        
        # Buscar la SVM
        svm = Svm.find(name=svm_name)
        if not svm:
            print(f"[ERROR] SVM '{svm_name}' not found")
            return False
        
        # Obtener el objeto SVM completo
        svm_obj = Svm(uuid=svm.uuid)
        
        # Configurar cada protocolo según el config.yaml
        for protocol, allowed in protocols_config.items():
            # Convertir el nombre del protocolo a minúsculas por si acaso
            protocol_name = protocol.lower()
            
            # Configurar el protocolo con el valor allowed
            setattr(svm_obj, protocol_name, {'allowed': allowed})
            
            status_text = "enabled" if allowed else "disabled"
            print(f"[*] Protocol {protocol_name.upper()}: {status_text}")
        
        # Aplicar cambios a la SVM
        print(f"[*] Applying protocol changes...")
        svm_obj.patch()
        
        print(f"[+] Protocol configuration applied successfully!")
        
        # GET: Obtener datos reales de la SVM con los protocolos desde la cabina
        print(f"[*] Retrieving protocol configuration from cluster...")
        svm_updated = Svm.find(name=svm_name)
        if svm_updated:
            # Obtener todos los campos de protocolos
            svm_updated.get(fields='nfs,cifs,fcp,iscsi,nvme,s3,ndmp')
            
            # Construir listas de protocolos permitidos y no permitidos
            allowed_protocols = []
            disallowed_protocols = []
            
            # Lista de protocolos conocidos en NetApp ONTAP
            protocol_fields = ['nfs', 'cifs', 'fcp', 'iscsi', 'nvme', 's3', 'ndmp']
            
            for protocol in protocol_fields:
                if hasattr(svm_updated, protocol):
                    protocol_obj = getattr(svm_updated, protocol)
                    if protocol_obj and hasattr(protocol_obj, 'allowed'):
                        if protocol_obj.allowed:
                            allowed_protocols.append(protocol)
                        else:
                            disallowed_protocols.append(protocol)
            
            # Extraer los datos para el show
            svm_data = {
                'vserver_name': svm_name,
                'vserver_uuid': svm_updated.uuid if hasattr(svm_updated, 'uuid') else 'N/A',
                'allowed_protocols': allowed_protocols,
                'disallowed_protocols': disallowed_protocols
            }
            
            # SHOW: Mostrar información como "vserver show -vserver <name> -instance"
            print(f"\n{'='*60}")
            print(f"  Protocol Configuration Show")
            print(f"{'='*60}")
            print(f"                   Vserver: {svm_data['vserver_name']}")
            print(f"              Vserver UUID: {svm_data['vserver_uuid']}")
            print(f"        Allowed Protocols: {', '.join(allowed_protocols) if allowed_protocols else 'none'}")
            print(f"     Disallowed Protocols: {', '.join(disallowed_protocols) if disallowed_protocols else 'none'}")
            print(f"{'='*60}\n")
            
            # Guardar en log con timestamp
            save_to_log('configure_protocols', svm_data)
        else:
            print(f"[WARNING] Could not retrieve protocol configuration")
        
        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp API error during protocol configuration")
        print(f"[ERROR] HTTP Status: {error.status_code}")
        
        if error.status_code == 400:
            print(f"[ERROR] Bad request - Invalid protocol configuration")
            print(f"[ERROR] Check that protocol names are valid")
        else:
            print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
        
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error during protocol configuration: {type(e).__name__}")
        print(f"[ERROR] Details: {str(e)}")
        return False


# ============================================================================
# FCP NETWORK INTERFACE CONFIGURATION FUNCTIONS
# ============================================================================

def create_network_interfaces(svm_name, net_interfaces_config):
    """
    Crea network interfaces (LIFs) usando API REST de ONTAP

    Args:
        svm_name: Nombre de la SVM
        net_interfaces_config: Lista de diccionarios con configuración de interfaces
    
    Returns:
        bool: True si todas se crearon exitosamente
    """
    try:
        # Validar que haya interfaces para crear
        if not net_interfaces_config:
            print(f"[WARNING] No network interfaces configured")
            return True
        
        print(f"\n[*] Creating {len(net_interfaces_config)} network interface(s) for SVM: {svm_name}")
        
        # Iterar por cada configuración de interfaz del config.yaml 
        for idx, interface_config in enumerate(net_interfaces_config, start=1):
            lif_name = interface_config.get('lif')
            data_protocol = interface_config.get('data_protocol')
            home_node = interface_config.get('home_node')
            home_port = interface_config.get('home_port')
            status_admin_value = interface_config.get('status_admin', 'down')
            
            # Convertir "up"/"down" a True/False
            if status_admin_value == 'up':
                status_admin = True
            else:
                status_admin = False
            
            if not all([lif_name, home_node, home_port]):
                print(f"[ERROR] Interface #{idx}: Missing required fields (lif, home_node, home_port)")
                return False
            
            print(f"\n[*] Creating interface #{idx}: {lif_name}")
            
            # Crear objeto FcInterface para protocolos FCP (SAN)
            net_interface = FcInterface()
            net_interface.name = lif_name
            net_interface.svm = {'name': svm_name}
            
            # Configurar location (home_node y home_port con node)
            net_interface.location = {
                'home_node': {'name': home_node},
                'home_port': {
                    'name': home_port,
                    'node': {'name': home_node}
                }
            }
            
            # Configurar data_protocol
            net_interface.data_protocol = data_protocol

            # Configurar status_admin para FC Interface
            net_interface.enabled = status_admin
            
            # POST a la API
            net_interface.post()
            
            print(f"[+] Interface '{lif_name}' created successfully")
        
        # GET: Obtener todas las FC interfaces de la SVM desde la cabina
        print(f"\n[*] Retrieving FC network interfaces from cluster...")
        interfaces_list = []
        
        fc_interfaces = FcInterface.get_collection(**{'svm.name': svm_name})
        for fc_lif in fc_interfaces:
            fc_lif.get()
            
            interface_data = {
                'vserver': svm_name,
                'interface': fc_lif.name,
                'status_admin': 'up' if fc_lif.enabled else 'down',
                'status_oper': fc_lif.state if hasattr(fc_lif, 'state') else 'N/A',
                'wwpn': fc_lif.wwpn if hasattr(fc_lif, 'wwpn') else 'N/A',
                'current_node': fc_lif.location.node.name if hasattr(fc_lif, 'location') and fc_lif.location.node else 'N/A',
                'current_port': fc_lif.location.port.name if hasattr(fc_lif, 'location') and fc_lif.location.port else 'N/A',
                'is_home': fc_lif.location.is_home if hasattr(fc_lif, 'location') and hasattr(fc_lif.location, 'is_home') else True,
                'data_protocol': fc_lif.data_protocol if hasattr(fc_lif, 'data_protocol') else 'fcp'
            }
            interfaces_list.append(interface_data)
        
        network_data = {
            'vserver_name': svm_name,
            'interfaces': interfaces_list,
            'total_interfaces': len(interfaces_list)
        }
        
        # SHOW: Mostrar como "network interface show -vserver <name>"
        print(f"\n{'='*100}")
        print(f"  Network Interface Show (FC)")
        print(f"{'='*100}")
        print(f"{'Vserver':<15} {'Interface':<20} {'Admin/Oper':<12} {'WWPN':<25} {'Node':<15} {'Port':<8} {'Home':<5}")
        print(f"{'-'*15} {'-'*20} {'-'*12} {'-'*25} {'-'*15} {'-'*8} {'-'*5}")
        
        for iface in interfaces_list:
            admin_oper = f"{iface['status_admin']}/{iface['status_oper']}"
            is_home_str = 'true' if iface['is_home'] else 'false'
            print(f"{iface['vserver']:<15} {iface['interface']:<20} {admin_oper:<12} {iface['wwpn']:<25} {iface['current_node']:<15} {iface['current_port']:<8} {is_home_str:<5}")
        
        print(f"{'='*100}\n")
        
        # Guardar en log con timestamp
        save_to_log('create_network_interfaces', network_data)
        
        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp API error")
        print(f"[ERROR] HTTP Status: {error.status_code}")
        print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error: {type(e).__name__}")
        print(f"[ERROR] Details: {str(e)}")
        return False


def create_management_interface(svm_name, mgmt_config):
    """
    Crea una interfaz de management (LIF) usando la API REST de ONTAP
    
    Args:
        svm_name: Nombre de la SVM
        mgmt_config: Diccionario con configuración de la interfaz del config.yaml
    
    Returns:
        bool: True si se creó exitosamente
    """
    try:
        # Validar que haya configuración para la interfaz de management
        if not mgmt_config:
            print(f"[WARNING] No management interface configured")
            return True
        
        # Extraer todos los parámetros del config.yaml 
        lif = mgmt_config.get('lif')
        service_policy = mgmt_config.get('service_policy')
        address = mgmt_config.get('address')
        netmask = mgmt_config.get('netmask')
        home_node = mgmt_config.get('home_node')
        home_port = mgmt_config.get('home_port')
        status_admin_value = mgmt_config.get('status_admin', 'up')
        auto_revert = mgmt_config.get('auto_revert', False)
        failover_group = mgmt_config.get('failover_group')
        
        # Convertir "up"/"down" a True/False
        if status_admin_value == 'up':
            status_admin = True
        else:
            status_admin = False
        
        # Validar campos obligatorios
        if not all([lif, service_policy, address, netmask, home_node, home_port]):
            print(f"[ERROR] Management interface: Missing required fields")
            print(f"[ERROR] Required: lif, service_policy, address, netmask, home_node, home_port")
            return False
        
        print(f"\n[*] Creating management interface: {lif}")
        print(f"[*] Service Policy: {service_policy}")
        print(f"[*] Address: {address}/{netmask}")
        print(f"[*] Home: {home_node}:{home_port}")
        print(f"[*] Auto Revert: {auto_revert}")
        print(f"[*] Status Admin: {status_admin}")

        if failover_group:
            print(f"[*] Failover Group: {failover_group}")
        
        # Crear objeto IpInterface usando la API REST
        interface = IpInterface()
        interface.name = lif
        interface.svm = {'name': svm_name}
        
        # Configurar dirección IP y máscara 
        interface.ip = {
            'address': address,
            'netmask': netmask
        }
        
        # Configurar location (home_node, home_port, auto_revert)
        interface.location = {
            'home_node': {'name': home_node},
            'home_port': {
                'name': home_port,
                'node': {'name': home_node}
            },
            'auto_revert': auto_revert
        }
        
        # Configurar service policy
        interface.service_policy = {'name': service_policy}
        
        # Configurar failover group si se especifica
        if failover_group:
            interface.location['failover_group'] = {'name': failover_group}
        
        # Configurar enabled (status-admin: up=true, down=false)
        interface.enabled = status_admin
        
        # POST a la API
        interface.post()
        
        print(f"[+] Management interface '{lif}' created successfully")
        
        # GET: Obtener la interfaz IP creada desde la cabina (filtrado por nombre)
        print(f"\n[*] Retrieving management interface from cluster...")
        ip_interface = IpInterface.find(name=lif, svm={'name': svm_name})
        
        if ip_interface:
            ip_interface.get()
            
            mgmt_data = {
                'vserver': svm_name,
                'interface': ip_interface.name,
                'status_admin': 'up' if ip_interface.enabled else 'down',
                'status_oper': ip_interface.state if hasattr(ip_interface, 'state') else 'N/A',
                'address': ip_interface.ip.address if hasattr(ip_interface, 'ip') and ip_interface.ip else 'N/A',
                'netmask': ip_interface.ip.netmask if hasattr(ip_interface, 'ip') and ip_interface.ip else 'N/A',
                'current_node': ip_interface.location.node.name if hasattr(ip_interface, 'location') and ip_interface.location.node else 'N/A',
                'current_port': ip_interface.location.port.name if hasattr(ip_interface, 'location') and ip_interface.location.port else 'N/A',
                'is_home': ip_interface.location.is_home if hasattr(ip_interface, 'location') and hasattr(ip_interface.location, 'is_home') else True,
                'service_policy': ip_interface.service_policy.name if hasattr(ip_interface, 'service_policy') and ip_interface.service_policy else 'N/A'
            }
            
            # SHOW: Mostrar como "network interface show -vserver <name> -lif <lif>"
            print(f"\n{'='*100}")
            print(f"  Network Interface Show (Management)")
            print(f"{'='*100}")
            print(f"{'Vserver':<15} {'Interface':<20} {'Admin/Oper':<12} {'Address/Mask':<22} {'Node':<15} {'Port':<8} {'Home':<5}")
            print(f"{'-'*15} {'-'*20} {'-'*12} {'-'*22} {'-'*15} {'-'*8} {'-'*5}")
            
            admin_oper = f"{mgmt_data['status_admin']}/{mgmt_data['status_oper']}"
            address_mask = f"{mgmt_data['address']}/{mgmt_data['netmask']}"
            is_home_str = 'true' if mgmt_data['is_home'] else 'false'
            
            print(f"{mgmt_data['vserver']:<15} {mgmt_data['interface']:<20} {admin_oper:<12} {address_mask:<22} {mgmt_data['current_node']:<15} {mgmt_data['current_port']:<8} {is_home_str:<5}")
            print(f"{'='*100}\n")
            
            # Guardar en log con timestamp
            save_to_log('create_management_interface', mgmt_data)
        else:
            print(f"[WARNING] Could not retrieve management interface details")
        
        return True
    
    # CONTROL DE ERRORES
    except NetAppRestError as error:
        print(f"[ERROR] NetApp API error")
        print(f"[ERROR] HTTP Status: {error.status_code}")
        if error.http_err_response and error.http_err_response.http_response:
            print(f"[ERROR] Details: {error.http_err_response.http_response.text}")
        else:
            print(f"[ERROR] Details: {str(error)}")
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error: {type(e).__name__}")
        print(f"[ERROR] Details: {str(e)}")
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

# SVM CREATION STEPS
# Crear la SVM
if create_svm(config_data['svm']):
    print("\n[SUCCESS] SVM creation completed!")
else:
    print("\n[FAILED] SVM creation failed")
    exit(1)

# Modificar la SVM
if modify_svm(config_data['svm']):
    print("\n[SUCCESS] SVM modification completed!")
else:
    print("\n[FAILED] SVM modification failed")
    exit(1)

# FCP SERVICE CREATION STEPS
# Crear servicio FCP en la SVM
if fcp_create(config_data['svm']):
    print("\n[SUCCESS] FCP service creation completed!")
else:
    print("\n[FAILED] FCP service creation failed")
    exit(1)

# Configurar protocolos permitidos en la SVM
if configure_protocols(config_data['svm']):
    print("\n[SUCCESS] Protocol configuration completed!")
else:
    print("\n[FAILED] Protocol configuration failed")
    exit(1)

# NETWORK INTERFACE CREATION STEPS
# Crear network interfaces
net_interfaces = config_data.get('net_interfaces', [])
if create_network_interfaces(config_data['svm']['name'], net_interfaces):
    print("\n[SUCCESS] Network interfaces creation completed!")
else:
    print("\n[FAILED] Network interfaces creation failed")
    exit(1)

# MANAGEMENT FCP NETWORK INTERFACE CREATION STEPS
# Crear management interface
mgmt_interface = config_data.get('mgmt_interface', {})
if create_management_interface(config_data['svm']['name'], mgmt_interface):
    print("\n[SUCCESS] Management interface creation completed!")
else:
    print("\n[FAILED] Management interface creation failed")
    exit(1)

# Obtener event logs de la cabina como backup
if get_event_logs(max_records=100):
    print("\n[SUCCESS] Event logs backup completed!")
else:
    print("\n[WARNING] Event logs backup failed (non-critical)")
