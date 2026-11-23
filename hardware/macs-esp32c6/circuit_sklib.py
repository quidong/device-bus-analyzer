from collections import defaultdict
from skidl import Pin, Part, Alias, SchLib, SKIDL, TEMPLATE

from skidl.pin import pin_types

SKIDL_lib_version = '0.0.1'

circuit = SchLib(tool=SKIDL).add_parts(*[
        Part(**{ 'name':'Conn_01x04', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'Conn_01x04'}), 'ref_prefix':'J', 'fplist':[''], 'footprint':'macs:RAST25_Direkt_1x04_K34', 'keywords':'connector', 'description':'', 'datasheet':'~', 'pins':[
            Pin(num='1',name='Pin_1',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='Pin_2',func=pin_types.PASSIVE,unit=1),
            Pin(num='3',name='Pin_3',func=pin_types.PASSIVE,unit=1),
            Pin(num='4',name='Pin_4',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'D_Zener', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'D_Zener'}), 'ref_prefix':'D', 'fplist':[''], 'footprint':'Diode_SMD:D_SOD-123F', 'keywords':'diode', 'description':'', 'datasheet':'~', 'pins':[
            Pin(num='1',name='K',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='A',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'D_Schottky', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'D_Schottky'}), 'ref_prefix':'D', 'fplist':[''], 'footprint':'Diode_SMD:D_SOD-123', 'keywords':'diode Schottky', 'description':'', 'datasheet':'~', 'pins':[
            Pin(num='1',name='K',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='A',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'SolderJumper_3_Bridged12', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'SolderJumper_3_Bridged12'}), 'ref_prefix':'JP', 'fplist':[''], 'footprint':'Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm', 'keywords':'Solder Jumper SPDT', 'description':'', 'datasheet':'~', 'pins':[
            Pin(num='1',name='A',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='C',func=pin_types.PASSIVE,unit=1),
            Pin(num='3',name='B',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'C', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'C'}), 'ref_prefix':'C', 'fplist':[''], 'footprint':'Capacitor_SMD:C_0603_1608Metric', 'keywords':'cap capacitor', 'description':'', 'datasheet':'~', 'pins':[
            Pin(num='1',name='~',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='~',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'AP63203WU', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'AP63203WU'}), 'ref_prefix':'U', 'fplist':['Package_TO_SOT_SMD:TSOT-23-6', 'Package_TO_SOT_SMD:TSOT-23-6'], 'footprint':'Package_TO_SOT_SMD:TSOT-23-6', 'keywords':'2A Buck DC/DC', 'description':'', 'datasheet':'https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf', 'pins':[
            Pin(num='1',name='FB',func=pin_types.INPUT,unit=1),
            Pin(num='2',name='EN',func=pin_types.INPUT,unit=1),
            Pin(num='3',name='IN',func=pin_types.PWRIN,unit=1),
            Pin(num='4',name='GND',func=pin_types.PWRIN,unit=1),
            Pin(num='5',name='SW',func=pin_types.OUTPUT,unit=1),
            Pin(num='6',name='BST',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'L', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'L'}), 'ref_prefix':'L', 'fplist':[''], 'footprint':'Inductor_SMD:L_1008_2520Metric', 'keywords':'inductor choke coil reactor magnetic', 'description':'', 'datasheet':'~', 'pins':[
            Pin(num='1',name='1',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='2',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'R', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'R'}), 'ref_prefix':'R', 'fplist':[''], 'footprint':'Resistor_SMD:R_0402_1005Metric', 'keywords':'R res resistor', 'description':'', 'datasheet':'~', 'pins':[
            Pin(num='1',name='~',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='~',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'LED', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'LED'}), 'ref_prefix':'D', 'fplist':[''], 'footprint':'LED_SMD:LED_0603_1608Metric', 'keywords':'LED diode', 'description':'', 'datasheet':'~', 'pins':[
            Pin(num='1',name='K',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='A',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'ESP32-C6-WROOM-1', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'ESP32-C6-WROOM-1'}), 'ref_prefix':'U', 'fplist':['macs:ESP32-C6-WROOM-1'], 'footprint':'macs:ESP32-C6-WROOM-1', 'keywords':'', 'description':'', 'datasheet':'https://documentation.espressif.com/esp32-c6-wroom-1_wroom-1u_datasheet_en.pdf', 'pins':[
            Pin(num='2',name='3V3',func=pin_types.PWRIN,unit=1),
            Pin(num='3',name='EN',func=pin_types.INPUT,unit=1),
            Pin(num='8',name='IO0',func=pin_types.BIDIR,unit=1),
            Pin(num='9',name='IO1',func=pin_types.BIDIR,unit=1),
            Pin(num='27',name='IO2',func=pin_types.BIDIR,unit=1),
            Pin(num='26',name='IO3',func=pin_types.BIDIR,unit=1),
            Pin(num='4',name='IO4',func=pin_types.BIDIR,unit=1),
            Pin(num='5',name='IO5',func=pin_types.BIDIR,unit=1),
            Pin(num='6',name='IO6',func=pin_types.BIDIR,unit=1),
            Pin(num='7',name='IO7',func=pin_types.BIDIR,unit=1),
            Pin(num='10',name='IO8',func=pin_types.BIDIR,unit=1),
            Pin(num='15',name='IO9',func=pin_types.BIDIR,unit=1),
            Pin(num='11',name='IO10',func=pin_types.BIDIR,unit=1),
            Pin(num='12',name='IO11',func=pin_types.BIDIR,unit=1),
            Pin(num='13',name='IO12/USB_D-',func=pin_types.BIDIR,unit=1),
            Pin(num='14',name='IO13/USB_D+',func=pin_types.BIDIR,unit=1),
            Pin(num='23',name='IO15',func=pin_types.BIDIR,unit=1),
            Pin(num='25',name='TXD0/IO16',func=pin_types.BIDIR,unit=1),
            Pin(num='24',name='RXD0/IO17',func=pin_types.BIDIR,unit=1),
            Pin(num='16',name='IO18',func=pin_types.BIDIR,unit=1),
            Pin(num='17',name='IO19',func=pin_types.BIDIR,unit=1),
            Pin(num='18',name='IO20',func=pin_types.BIDIR,unit=1),
            Pin(num='19',name='IO21',func=pin_types.BIDIR,unit=1),
            Pin(num='20',name='IO22',func=pin_types.BIDIR,unit=1),
            Pin(num='21',name='IO23',func=pin_types.BIDIR,unit=1),
            Pin(num='1',name='GND',func=pin_types.PWRIN,unit=1),
            Pin(num='28',name='GND',func=pin_types.PASSIVE,unit=1),
            Pin(num='29',name='GND',func=pin_types.PASSIVE,unit=1),
            Pin(num='22',name='NC',func=pin_types.NOCONNECT,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'SW_Push', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'SW_Push'}), 'ref_prefix':'SW', 'fplist':[''], 'footprint':'macs:SW_TS-3025', 'keywords':'switch normally-open pushbutton push-button', 'description':'', 'datasheet':'~', 'pins':[
            Pin(num='1',name='1',func=pin_types.PASSIVE),
            Pin(num='2',name='2',func=pin_types.PASSIVE)], 'unit_defs':[] }),
        Part(**{ 'name':'USB_C_Receptacle_USB2.0_16P', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'USB_C_Receptacle_USB2.0_16P'}), 'ref_prefix':'J', 'fplist':[''], 'footprint':'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12', 'keywords':'usb universal serial bus type-C USB2.0', 'description':'', 'datasheet':'https://www.usb.org/sites/default/files/documents/usb_type-c.zip', 'pins':[
            Pin(num='A1',name='GND',func=pin_types.PASSIVE,unit=1),
            Pin(num='A12',name='GND',func=pin_types.PASSIVE,unit=1),
            Pin(num='A4',name='VBUS',func=pin_types.PASSIVE,unit=1),
            Pin(num='A5',name='CC1',func=pin_types.BIDIR,unit=1),
            Pin(num='A6',name='D+',func=pin_types.BIDIR,unit=1),
            Pin(num='A7',name='D-',func=pin_types.BIDIR,unit=1),
            Pin(num='A8',name='SBU1',func=pin_types.BIDIR,unit=1),
            Pin(num='A9',name='VBUS',func=pin_types.PASSIVE,unit=1),
            Pin(num='B1',name='GND',func=pin_types.PASSIVE,unit=1),
            Pin(num='B12',name='GND',func=pin_types.PASSIVE,unit=1),
            Pin(num='B4',name='VBUS',func=pin_types.PASSIVE,unit=1),
            Pin(num='B5',name='CC2',func=pin_types.BIDIR,unit=1),
            Pin(num='B6',name='D+',func=pin_types.BIDIR,unit=1),
            Pin(num='B7',name='D-',func=pin_types.BIDIR,unit=1),
            Pin(num='B8',name='SBU2',func=pin_types.BIDIR,unit=1),
            Pin(num='B9',name='VBUS',func=pin_types.PASSIVE,unit=1),
            Pin(num='S1',name='SHIELD',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'USBLC6-2SC6', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'USBLC6-2SC6'}), 'ref_prefix':'U', 'fplist':['Package_TO_SOT_SMD:SOT-666', 'Package_TO_SOT_SMD:SOT-23-6'], 'footprint':'Package_TO_SOT_SMD:SOT-23-6', 'keywords':'usb ethernet video', 'description':'', 'datasheet':'https://www.st.com/resource/en/datasheet/usblc6-2.pdf', 'pins':[
            Pin(num='1',name='I/O1',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='GND',func=pin_types.PASSIVE,unit=1),
            Pin(num='3',name='I/O2',func=pin_types.PASSIVE,unit=1),
            Pin(num='4',name='I/O2',func=pin_types.PASSIVE,unit=1),
            Pin(num='5',name='VBUS',func=pin_types.PASSIVE,unit=1),
            Pin(num='6',name='I/O1',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'MMBT3904', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'MMBT3904'}), 'ref_prefix':'Q', 'fplist':['Package_TO_SOT_SMD:SOT-23', 'Package_TO_SOT_SMD:SOT-23'], 'footprint':'Package_TO_SOT_SMD:SOT-23', 'keywords':'NPN Transistor', 'description':'', 'datasheet':'https://www.onsemi.com/pdf/datasheet/pzt3904-d.pdf', 'pins':[
            Pin(num='1',name='B',func=pin_types.INPUT,unit=1),
            Pin(num='2',name='E',func=pin_types.PASSIVE,unit=1),
            Pin(num='3',name='C',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'AO3401A', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'AO3401A'}), 'ref_prefix':'Q', 'fplist':['Package_TO_SOT_SMD:SOT-23', 'Package_TO_SOT_SMD:SOT-23'], 'footprint':'Package_TO_SOT_SMD:SOT-23', 'keywords':'P-Channel MOSFET', 'description':'', 'datasheet':'http://www.aosmd.com/pdfs/datasheet/AO3401A.pdf', 'pins':[
            Pin(num='1',name='G',func=pin_types.INPUT,unit=1),
            Pin(num='2',name='S',func=pin_types.PASSIVE,unit=1),
            Pin(num='3',name='D',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'TestPoint', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'TestPoint'}), 'ref_prefix':'TP', 'fplist':[''], 'footprint':'TestPoint:TestPoint_Pad_D1.0mm', 'keywords':'test point tp', 'description':'', 'datasheet':'~', 'pins':[
            Pin(num='1',name='1',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] })])