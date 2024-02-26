#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

num_interfaces = 4
# a dictionary that maps a mac address to an interface
mac_table = {}
# a dictionary that maps an interface to a vlan id/state
vlan_ids = {}
# a dictionary that maps an interface to a state
interface_states = {}

root_bridge_ID, own_bridge_ID, root_path_cost, root_port = 0, 0, 0, 0

def init(priority):
    for i in range(0, num_interfaces):
        if vlan_ids[i] == 'T':
            interface_states[i] = 'BLK'

    global root_bridge_ID, own_bridge_ID
    own_bridge_ID = int(priority)
    root_bridge_ID = int(priority)

    # since our switch is the root, all trunk ports will become designated
    if root_bridge_ID == own_bridge_ID:
        for i in range(0, num_interfaces):
            if vlan_ids[i] == 'T':
                interface_states[i] = 'LSN'

def parse_config(switch_id):
    # search for the interface in the trunk list
    with open('configs/switch' + switch_id + '.cfg') as f:
        for line in f:
            # if line contains one word, its the priority
            if len(line.split()) == 1:
                priority = line.split()[0]
            else:
                # get the interface by searching by its name
                for i in range(0, num_interfaces):
                    if line.split()[0] == get_interface_name(i):
                        interface = i
                # if second word is T, add to vlan_ids as trunk
                if line.split()[1] == 'T':
                    vlan_ids[interface] = 'T'
                # if second word is A, add to vlan_ids as access
                else:
                    vlan_ids[interface] = line.split()[1]
    return priority

def create_vlan_tag(vlan_id):
    # 0x8200 for the Ethertype for 802.1Q
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def change_tag(interfaceS, interfaceD, data, length):
    if vlan_ids[interfaceS] != 'T':
        # sourse = access
        if vlan_ids[interfaceD] == 'T':
            # dest = trunk, adding tag
            data = data[0:12] + create_vlan_tag(int(vlan_ids[interfaceS])) + data[12:]
            length += 4
        elif vlan_ids[interfaceS] != vlan_ids[interfaceD]:
            length = 0
    else:
        # source = trunk
        if vlan_ids[interfaceD] != 'T':
            # dest = access, removing tag
            vlan_id = int.from_bytes(data[14:16], byteorder='big') & 0x0FFF
            if vlan_id != int(vlan_ids[interfaceD]):
                length = 0
            else:
                data = data[0:12] + data[16:]
                length -= 4
    return data, length

def populate_mac_table(src_mac, dst_mac, interface, data, length):
    # the source mac is added to the mac table
    mac_table[src_mac] = interface
    no_uni_dest = True

    # if the destination is a unicast address, check if it is in the mac table
    if src_mac[0] != 0xff:
        if dst_mac in mac_table:
            (data1, length1) = change_tag(interface, mac_table[dst_mac], data, length)
            if length1 != 0:
                send_to_link(mac_table[dst_mac], data1, length1)
            no_uni_dest = False

    # if not, time to flood
    if no_uni_dest:
        for i in range(0, num_interfaces):
            if i != interface:
                if vlan_ids[i] != 'T' or (vlan_ids[i] == 'T' and interface_states[i] == 'LSN'):
                    (data1, length1) = change_tag(interface, i, data, length)
                    if length1 != 0:
                        send_to_link(i, data1, length1)

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def create_bdpu(root_id, sender_id, root_path_cost, port):
    destination = b'\x01\x80\xc2\x00\x00\x00'
    source = get_switch_mac()

    LLC_LENGTH = struct.pack('!H', 0x26)
    LLC_HEADER = b'\x42\x42\x03'
    PROTO_ID = struct.pack('!H', 0x0000)
    VERSION = struct.pack('!B', 0x00)
    BPDU_TYPE = struct.pack('!B', 0x00)
    FLAGS = struct.pack('!B', 0x00)

    ROOT_ID = struct.pack('!B', root_id) + b'\x00\x00\x00\x00\x00\x00\x00'
    ROOT_PATH_COST = struct.pack('!i', root_path_cost)
    BRIDGE_ID = struct.pack('!B', sender_id) + b'\x00\x00\x00\x00\x00\x00\x00'
    PORT_ID = struct.pack('!H', port)

    MESSAGE_AGE = struct.pack('!H', 0x00)
    MAX_AGE = struct.pack('!H', 0x00)
    HELLO_TIME = struct.pack('!H', 0x00)
    FORWARD_DELAY = struct.pack('!H', 0x00)

    return destination + source + LLC_LENGTH + LLC_HEADER + PROTO_ID + VERSION + BPDU_TYPE + FLAGS + ROOT_ID + ROOT_PATH_COST + BRIDGE_ID + PORT_ID + MESSAGE_AGE + MAX_AGE + HELLO_TIME + FORWARD_DELAY

def send_bdpu_every_sec():
    while True:
        # TODO Send BDPU every second if necessary
        if own_bridge_ID == root_bridge_ID:
            for i in range(0, num_interfaces):
                if vlan_ids[i] == 'T':
                    send_to_link(i, create_bdpu(own_bridge_ID, own_bridge_ID, 0, 0), 52)
        time.sleep(1)

def analyze_bpdu(interface, data, length):
    # TODO Analyze BPDU and update the state of the interfaces
    root_id = int.from_bytes(data[22:23], byteorder='little')
    path_cost = int.from_bytes(data[30:34], byteorder='big')
    sender_id = int.from_bytes(data[34:35], byteorder='little')
    # port = int.from_bytes(data[42:44], byteorder='big')

    global root_bridge_ID, root_path_cost, root_port

    if root_id < root_bridge_ID:
        root_path_cost = path_cost + 10
        root_port = interface

        # if we were the Root Bridge
        if root_bridge_ID == own_bridge_ID:
            for i in range(0, num_interfaces):
                if vlan_ids[i] == 'T' and i != root_port:
                    interface_states[i] = 'BLK'
        root_bridge_ID = root_id
        
        if interface_states[root_port] == 'BLK':
            interface_states[root_port] = 'LST'
        
        # Update and forward this BPDU to all other trunk ports
        for i in range(0, num_interfaces):
            if vlan_ids[i] == 'T' and i != interface:
                send_to_link(i, create_bdpu(root_bridge_ID, own_bridge_ID, root_path_cost, root_port), 52)
    elif root_id == root_bridge_ID:
        if interface_states[interface] == root_port and path_cost + 10 < root_path_cost:
            root_path_cost = path_cost + 10
            
        elif interface_states[interface] != root_port:
            if path_cost > root_path_cost:
                if interface_states[interface] != 'LST':
                    interface_states[interface] = 'LST'
    elif sender_id == own_bridge_ID:
        interface_states[interface] == 'BLK'
    else:
        return

    if own_bridge_ID == root_bridge_ID:
        for i in range(0, num_interfaces):
            if vlan_ids[i] == 'T':
                interface_states[i] = 'LSN'

def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    switch_id = sys.argv[1]

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)

    # Parse the config file for VLAN IDs
    priority = parse_config(switch_id)

    # Initialize the switch for STP
    init(priority)

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec)
    t.start()

    while True:
        interface, data, length = recv_from_any_link()
        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        # Print the MAC src and MAC dst in human readable format
        dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac = ':'.join(f'{b:02x}' for b in src_mac)

        # check if packet is a BPDU
        if dest_mac == '01:80:c2:00:00:00':
            analyze_bpdu(interface, data, length)
        else:
            populate_mac_table(src_mac, dest_mac, interface, data, length)

if __name__ == "__main__":
    main()
