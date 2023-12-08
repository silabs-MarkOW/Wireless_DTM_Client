import sys
import bgapi
import getopt
import time
import argparse
from inspect import getframeinfo, stack

service_uuid_strs = {
    'DTM_CONTROL':'0d8991ee-e355-47eb-8810-ea89a67dddeb',
    'DTM_RX'     :'bace30ed-7375-4b90-accd-1867f7d0f073',
    'DTM_TX'     :'ef0ef18f-8a97-4021-9281-fddb09cd0f71'
}

characteristic_uuid_strs = {
    'DTM_CONTROL': {
        'MODE'     : 'ceef39e8-590b-4b41-9345-fc5241124eef',
        'DURATION' : '5ed6dc96-d00c-4ee6-9904-2d8ef4869c3c',
        'RESULT'   : '84d0e28a-b25b-4188-896d-f3f6bd3425f6'
        },
    'DTM_RX'     : {
        'CHANNEL' : '7170ea45-b74a-49d9-8fb9-7d9b6b6e26c9',
        'PHY'     : 'f133d930-eb80-4254-adbf-7915e90a554d'
        },
    'DTM_TX'     : {
        'PACKET_TYPE' : '31d511a9-a3f4-4cdd-b823-58b2ed1153d9',
        'LENGTH'      : 'e4a01204-d8c5-420f-ad9b-418692137ea0',
        'CHANNEL'     : '1928cd35-1ac2-4acd-9c70-324cae69dbda',
        'PHY'         : 'd559d164-9d6a-40d6-93e6-f0745d104a0a',
        'POWER'       : 'a3932ee9-9fe4-49ab-ba6f-3e6be4fa74cc'
        }
}

packet_types = ['prbs9', '11110000', '10101010', '11111111', '00000000', '00001111', '01010101', 'pn9', 'carrier']

def uuid_str_to_int(uuid_str) :
    tokens = uuid_str.split('-')
    sum = 0
    for token in tokens :
        sum <<= (len(token) << 2)
        sum += int(token,16)
    return sum

service_uuids = {}
for key in service_uuid_strs :
    service_uuids[key] = uuid_str_to_int(service_uuid_strs[key])
characteristic_uuids = {}
for skey in characteristic_uuid_strs :
    characteristic_uuids[skey] = {}
    for key in characteristic_uuid_strs[skey] :
        characteristic_uuids[skey][key] = uuid_str_to_int(characteristic_uuid_strs[skey][key])
        
current_service = None
filters = ['bt_name','bt_address']
services = {}
characteristics = {}
characteristic_values = {}
services_to_discover = []
characteristics_to_write = []
characteristics_to_read = []
time_start = None
time_stop = None

def enqueue_writes() :
    global characteristics_to_write
    characteristics_to_write.append('DTM_CONTROL.MODE')
    characteristics_to_write.append('DTM_CONTROL.DURATION')
    if 'rx' == args.mode :
        characteristics_to_write.append('DTM_RX.CHANNEL')
        characteristics_to_write.append('DTM_RX.PHY')
    else :
        characteristics_to_write.append('DTM_TX.CHANNEL')
        characteristics_to_write.append('DTM_TX.PHY')
        characteristics_to_write.append('DTM_TX.PACKET_TYPE')
        characteristics_to_write.append('DTM_TX.LENGTH')
        characteristics_to_write.append('DTM_TX.POWER')

def enqueue_reads() :
    global characteristics_to_read
    characteristics_to_read.append('DTM_CONTROL.RESULT')
    characteristics_to_read.append('DTM_CONTROL.MODE')
    characteristics_to_read.append('DTM_CONTROL.DURATION')
    if 'rx' == args.mode :
        characteristics_to_read.append('DTM_RX.CHANNEL')
        characteristics_to_read.append('DTM_RX.PHY')
    else :
        characteristics_to_read.append('DTM_TX.CHANNEL')
        characteristics_to_read.append('DTM_TX.PHY')
        characteristics_to_read.append('DTM_TX.PACKET_TYPE')
        characteristics_to_read.append('DTM_TX.POWER')
    if 'tx' == args.mode :
        characteristics_to_read.append('DTM_TX.LENGTH')
        
def write_next_characteristic(connection) :
    global characteristics_to_write
    if 0 == len(characteristics_to_write) :
        return False
    id = characteristics_to_write.pop()
    tokens = id.split('.')
    if 2 != len(tokens) :
        raise RunTimeError(tokens.__str__())
    uuid = characteristic_uuids[tokens[0]][tokens[1]]
    handle = characteristics[tokens[0]][uuid]
    if 'MODE' == tokens[1] :
        modes = ['None','rx','tx','cw']
        value = modes.index(args.mode).to_bytes(1,'little')
    elif 'DURATION' == tokens[1] :
        value = args.duration.to_bytes(2,'little')
    elif 'CHANNEL' == tokens[1] :
        value = args.channel.to_bytes(1,'little')
    elif 'PHY' == tokens[1] :
        phys = ['None','1m','2m','125k','500k']
        value = phys.index(args.phy).to_bytes(1,'little')
    elif 'PACKET_TYPE' == tokens[1] :
        index = packet_types.index(args.packet_type)
        if index > 2 :
            index += 1  # skip 3
        if 8 == index :
            index = 0xfd
        if 9 == index :
            index = 0xfe
        value = index.to_bytes(1,'little')
    elif 'LENGTH' == tokens[1] :
        value = args.length.to_bytes(1,'little')
    elif 'POWER' == tokens[1] :
        value = args.power.to_bytes(1,'little')
    else :
        raise RuntimeError('Mishandled %s'%(id))
    if args.verbose > 1 :
        print('%s: write %s to handle %d'%(id,value.__str__(),handle))
    dev.bt.gatt.write_characteristic_value(connection,handle,value)
    return True

def read_next_characteristic(connection) :
    global characteristics_to_read
    if 0 == len(characteristics_to_read) :
        return False
    id = characteristics_to_read.pop()
    tokens = id.split('.')
    if 2 != len(tokens) :
        raise RunTimeError(tokens.__str__())
    uuid = characteristic_uuids[tokens[0]][tokens[1]]
    handle = characteristics[tokens[0]][uuid]
    dev.bt.gatt.read_characteristic_value(connection,handle)
    return True

def display_results() :
    print('Observed duration of no advertisement: %.1f seconds'%(time_stop - time_start))
    uuid = characteristic_uuids['DTM_CONTROL']['RESULT']
    handle = characteristics['DTM_CONTROL'][uuid]
    value = characteristic_values.get(handle)
    if None == value :
        raise RuntimeError('DTM_CONTROL.RESULT missing')
    print('DTM_CONTROL.RESULT: %d'%(int.from_bytes(value,'little')))
    for skey in characteristic_uuids :
        for key in characteristic_uuids[skey] :
            if 'DTM_CONTROL' == skey :
                if 'RESULT' == key :
                    continue # already shown
            uuid = characteristic_uuids[skey][key]
            handle = characteristics[skey][uuid]
            value = characteristic_values.get(handle)
            if None == value :
                continue
            value = int.from_bytes(value,'little')
            print('%s.%s: %d'%(skey,key,value))
    
OTA_SERVICE_UUID = 0x1d14d6eefd634fa1bfa48f47b42119f0
OTA_CONTROL_UUID = 0xf7bf3564fb6d4e5388a45e37e0326063
ignored_events = ['bt_evt_connection_parameters',
                  'bt_evt_connection_phy_status',
                  'bt_evt_connection_data_length',
                  'bt_evt_connection_remote_used_features']

xapi = 'sl_bt.xapi'
connector = None
baudrate = 115200
target = {'address':None}
state = 'start'
timeout = None
app_rssi = None
ota_mode = False
match_service = 0x1509
match_name = None
list_mode = False
devices = {}

def valid_channel(s) :
    value = int(s)
    if value < 0 or value > 39 :
        raise argparse.ArgumentTypeError('valid channels are in range {0...39}')
    return value

def valid_duration(s) :
    value = int(s)
    max = (1 << 16) -1
    if value < 1 or value > max :
        raise argparse.ArgumentTypeError('valid durations are in range {1...%d}'%(max))
    return value

def valid_length(s) :
    value = int(s)
    max = 255
    if value < 1 or value > max :
        raise argparse.ArgumentTypeError('valid lengths are in range {1...%d}'%(max))
    return value

parser = argparse.ArgumentParser()
parser.add_argument('--xapi',default='sl_bt.xapi',help='path to XAPI file (see ${GSDK}/protocol/api)')
parser.add_argument('--bt-address',help='Bluetooth peripheral address')
parser.add_argument('--bt-name',help='Complete Local Name advertised by device')
parser.add_argument('--scan-timeout',type=float,default=5,help='Duration of scan')
parser.add_argument('--wstk-address',help='TCP/IP address for NCP communication')
parser.add_argument('--uart',help='Port for NCP communication')
parser.add_argument('--baudrate',type=int,default=115200,help='baudrate of NCP UART')
parser.add_argument('-v','--verbose',action='count',default=0,help='Verbose level')
parser.add_argument('--mode',required=True,choices=['rx','tx','cw'],help='DTM test mode')
parser.add_argument('--channel',required=True,type=valid_channel,help='channel {0...39}')
parser.add_argument('--phy',required=True,choices=['1m','2m','125k','500k'],help='PHY used')
parser.add_argument('--duration',required=True,type=valid_duration,help='Duration of DTM operation in seconds, 1...65535')
parser.add_argument('--length',type=valid_length,help='packet length, 1...255')
parser.add_argument('--power',type=int,help='TX Power in ddBm')
parser.add_argument('--packet-type',choices=packet_types,help='TX payload')

args = parser.parse_args()
if None == args.wstk_address :
    if None == args.uart :
        print('Either --wstk_address or --uart is required')
        parser.print_usage()
        quit()
    else :
        connector = bgapi.SerialConnector(args.uart,baudrate=args.baudrate)
else :
    if None == args.uart :
        connector = bgapi.SocketConnector((args.wstk_address,4901))
    else :
        print('Either --wstk_address or --uart is required')
        
if None != args.bt_address and None != args.bt_name :
    print('Both --bt-addess and --bt-name supplied, match requires both')

if 'tx' == args.mode or 'cw' == args.mode :
    if None == args.packet_type :
        parser.print_usage()
        print('Error: --packet-type is required for TX/CW modes')
        quit()
    if None == args.power :
        parser.print_usage()
        print('Error: --power is required for TX/CW modes')
        quit()

if 'tx' == args.mode :
    if None == args.length :
        parser.print_usage()
        print('Error: --length is required for TX modes')
        quit()
    
#print(args)

try :
    dev = bgapi.BGLib(connection=connector,apis=args.xapi)
except FileNotFoundError :
    parser.print_usage()
    print('xml file defining API, %s, not found. See -x option'%(args.xapi))
    quit()
    
def setState(new_state) :
    global state
    confused = 'confused' == new_state
    caller = getframeinfo(stack()[1][0])
    if args.verbose > 0 or confused :
        print('%s:%d:set_state: %s -> %s'%(caller.filename,caller.lineno,state,new_state))
    if confused or args.verbose > 3 :
        s = stack()
        for si in s[1:] :
            caller = getframeinfo(si[0])
            print('%s:%d:%s'%(caller.filename,caller.lineno,caller.function))
    state = new_state

def process_adData(adData) :
    rc = {}
    while len(adData) :
        length = adData[0]
        type = adData[1]
        if length > len(adData[1:]) :
            return {}
        payload = adData[2:2+length-1]
        adData = adData[1+length:]
        if 1 == type :
            rc['Flags'] = payload[0]
        elif 2 == (type & 0xfe) :
            label = ['Inc','C'][type & 1]+'ompleteListOf16bitServices'
            services = {}
            while len(payload) :
                uuid = int.from_bytes(payload[0:2],'little')
                payload = payload[2:]
                services[uuid] = True
                rc[label] = services
        elif 9 == type :
            rc['CompleteLocalName'] = payload.decode()
    return rc

def updateTargetRssi(rssi,channel) :
    global target
    if None == channel :
        target['rssi'].append(rssi)
    else :
        target['rssi'][channel].append(rssi)

def clearTargetRssi() :
    global target
    rssi = target.get('rssi')
    if None == rssi : return setState('confused')
    if dict == type(rssi) :
        target['rssi'] = {37:[],38:[],39:[]}
    elif list == type(rssi) :
        target['rssi'] = []
    else :
        setState('confused')
        
def connectTarget() :
    dev.bt.connection.open(target['address'],target['address_type'],1)
    setState('connecting')

def setTarget(address,address_type,rssi,channel) :
    global target
    global timeout
    if args.verbose > 0 :
        print('Target address: %s'%(address))
    target['address'] = address
    target['address_type'] = address_type
    connectTarget()
    return
    if None == channel :
        target['rssi'] = []
    else :
        target['rssi'] = {37:[],38:[],39:[]}
    updateTargetRssi(rssi,channel)
    timeout = time.time() + args.monitor_timeout
    setState('watching-app')


def rssi_stats(obj) :
    sum = 0
    count = 0
    if dict == type(obj) :
        for ch in obj :
            for rssi in obj[ch] :
                sum += rssi
                count +=1
    elif list == type(obj) :
        for rssi in obj :
            sum += rssi
            count += 1
    else :
        raise RuntimeError('confusion is not enough')
    return count,sum

def process_rssi() :
    if ota_mode :
        app_count,app_sum = rssi_stats(app_rssi)
        ota_count,ota_sum = rssi_stats(target['rssi'])
        app_mean = app_sum/app_count
        ota_mean = ota_sum/ota_count
        print('%d second duration: application %d packets, RSSI average %.1f, AppLoader %d packets, RSSI average %.1f (delta: %.1f dB)'%(duration,app_count,app_mean,ota_count,ota_mean,ota_mean-app_mean))
    else :
        count,sum = rssi_stats(target['rssi'])
        print('%d second  duration: %d packets, RSSI average %.1f, '%(duration,count,sum/count))
    setState('done')

def list_devices() :
    for addr in devices :
        str = addr
        name = devices[addr].get('CompleteLocalName')
        services = devices[addr].get('services')
        if None != name : str += ' Complete Local Name: %s'%(name)
        print(str)
        
def process_advertisement(addr,addrType,rssi,adData,channel=None) :
    global time_stop
    mismatch = False
    if time.time() > timeout :
        dev.bt.scanner.stop()
        setState('scanning-timeout')
        list_devices()
        return False
    data = None
    if None == devices.get(addr) :
        data = process_adData(adData)
        devices[addr] = data
    if None != args.bt_address :
        if addr != args.bt_address :
            mismatch = True
    if None != args.bt_name :
        if None == data :
            data = process_adData(adData)
        name = data.get('CompleteLocalName')
        if args.bt_name != name :
            mismatch = True
    if 'searching' == state and not mismatch :
        time_stop = time.time()
        dev.bt.scanner.stop()
        setTarget(addr,addrType,rssi,channel)

def setTargetService(handle,uuid) :
    global target
    services = target.get('services')
    if None == services :
        services = {}
    services[uuid] = {'handle':handle,'characteristics':{}}
    target['services'] = services
    #print('uuid: 0x%x'%(uuid))
    
def discover_ota(connection) :
    global target
    services = target.get('services')
    if None == services : return setState('confused')
    target['current-service-uuid'] = OTA_SERVICE_UUID
    ota_service = services.get(target['current-service-uuid'])
    if None == ota_service : return setState('confused')
    handle = ota_service.get('handle')
    if None == handle : return setService('confused')
    dev.bt.gatt.discover_characteristics(connection,handle)
    setState('discovering-ota-characteristics')

def setTargetCharacteristic(handle,uuid,properties) :
    services = target.get('services')
    if None == services : return setState('confused')
    currentService = target.get('current-service-uuid')
    if None == currentService : return setState('confused')
    ota_service = services.get(currentService)
    if None == ota_service : return setState('confused')
    characteristics = ota_service.get('characteristics')
    if None == characteristics : return setState('confused')
    characteristics[uuid] = {'handle':handle,'descriptors':{},'properties':properties}
    
def initiate_ota(connection) :
    global target
    services = target.get('services')
    if None == services : return setState('confused')
    ota_service = services.get(target['current-service-uuid'])
    if None == ota_service : return setState('confused')
    characteristics = ota_service.get('characteristics')
    if None == characteristics : return setState('confused')
    ota_control = characteristics.get(OTA_CONTROL_UUID)
    if None == ota_control : return setState('confused')
    handle = ota_control.get('handle')
    if None == handle : return setState('confused')
    dev.bt.gatt.write_characteristic_value(connection,handle,b'\x00')
    setState('writing-ota-control')

def dump_gatt() :
    services = target['services']
    print(services)
    for s in services :
        print('Service UUID 0x%X'%(s))
        characteristics = services[s]['characteristics']
        for c in characteristics :
            print('  Characteristic UUID 0x%X, properties: 0x%x'%(c,characteristics[c]['properties']))

def is_advertising_report(evt) :
    if 'bt_evt_scanner_legacy_advertisement_report' == evt :
        return True
    if 'bt_evt_scanner_scan_report' == evt :
        return True
    return False

def sl_bt_on_event(evt) :
    global app_rssi
    global timeout
    global services
    global current_service
    global characteristics
    global services_to_discover
    global time_start
    if (args.verbose > 1 and not is_advertising_report(evt)) or args.verbose > 2 :
        print(evt)
    if 'bt_evt_system_boot' == evt :
        if args.verbose > 0 :
            print('system-boot: BLE SDK %dv%dp%db%d'%(evt.major,evt.minor,evt.patch,evt.build))
        dev.bt.scanner.start(1,2)
        scan_mode = 'observing'
        for key in filters :
            if None != args.__dict__[key] :
                scan_mode = 'searching'
                break
        setState(scan_mode)
        timeout = time.time() + args.scan_timeout
    elif is_advertising_report(evt) :
        process_advertisement(evt.address,evt.address_type,evt.rssi,evt.data,evt.channel)
        if 'scanning-timeout' == state :
            return False
    elif 'bt_evt_connection_opened' == evt :
        if 'connecting' != state :
            setState('confused')
        setState('connected')
    elif 'bt_evt_gatt_mtu_exchanged' == evt :
        if 0 == len(services) :
            setState('discovering-services')
            dev.bt.gatt.discover_primary_services(evt.connection)
        else :
            setState('reading-characteristics')
            enqueue_reads()
            read_next_characteristic(evt.connection)
    elif 'bt_evt_gatt_service' == evt :
        uuid = int.from_bytes(evt.uuid,'little')
        services[uuid] = evt.service
    elif 'bt_evt_gatt_characteristic' == evt :
        characteristics[current_service][int.from_bytes(evt.uuid,'little')] = evt.characteristic
    elif 'bt_evt_gatt_characteristic_value' == evt :
        characteristic_values[evt.characteristic] = evt.value
    elif 'bt_evt_gatt_procedure_completed' == evt:
        unexpected = True
        if 'discovering-services' == state :
            unexpected = False
            services_to_discover = []
            for id in service_uuids :
                services_to_discover.append(id)
            setState('discovering-characteristics')
        if 'discovering-characteristics' == state :
            unexpected = False
            if len(services_to_discover) > 0 :
                current_service = services_to_discover.pop()
                characteristics[current_service] = {}
                dev.bt.gatt.discover_characteristics(evt.connection,services[service_uuids[current_service]])
            else :
                enqueue_writes()
                if args.verbose > 3 :
                    print(characteristics_to_write)
                    print(characteristics)
                setState('writing-characteristics')
        if 'writing-characteristics' == state :
            unexpected = False
            if not write_next_characteristic(evt.connection) :
                dev.bt.connection.close(evt.connection)
                setState('expecting-close-to-execute')
        if 'reading-characteristics' == state :
            unexpected = False
            if not read_next_characteristic(evt.connection) :
                dev.bt.connection.close(evt.connection)
                setState('expecting-close-done')            
        if unexpected :
            setState('confused')
    elif 'bt_evt_connection_closed' == evt :
        if 'expecting-close-to-execute' == state :
            dev.bt.scanner.start(1,2)
            scan_mode = 'searching'
            setState(scan_mode)
            time_start = time.time()
            timeout = time_start + args.duration + args.scan_timeout
            print('waiting %d seconds for result'%(args.duration))
        elif 'expecting-close-done' == state :
            display_results()
            return False
        else :
            print('Unexpected connection loss, readon: 0x%x'%(evt.reason))
            setState('confused')
            return False
    else :
        unhandled = True
        for ignore in ignored_events :
            if ignore == evt :
                unhandled = False
        if unhandled :
            print('Unhandled event: %s'%(evt.__str__()))
    return state != 'confused'

dev.open()
dev.bt.system.reset(0)
setState('reset')

# keep scanning for events
while 'done' != state :
    try:
        # print('Starting point...')
        evt = dev.get_events(max_events=1)
        if evt:
            if not sl_bt_on_event(evt[0]) :
                break
    except(KeyboardInterrupt, SystemExit) as e:
        if dev.is_open():
            dev.close()
            print('Exiting...')
            sys.exit(1)

if dev.is_open():
    dev.close()

