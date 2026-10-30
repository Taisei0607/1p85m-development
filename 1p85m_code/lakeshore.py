import socket
import time
from datetime import datetime
import ipaddress
from scapy.all import ARP, Ether, conf, srp

TARGET_MAC = "00:21:69:01:37:1E"
NETWORK = "192.168.0.0/24"
GPIB_ADDRESS = 12 # 仮の値。本体のIEEE Addressに合わせる

def find_ip_by_mac(mac, network):
    target = mac.lower().replace("-", ":")
    subnet = ipaddress.IPv4Network(network, strict = False)

    if subnet.num_addresses > 4096:
        raise ValueError("探索範囲が広すぎます。対象のLANに絞ってください。")

    probe_ip = str(subnet.network_address + 1)
    iface, source_ip, gateway = conf.route.route(probe_ip)

    if gateway != "0.0.0.0":
        raise RuntimeError("指定範囲はルーター経由です。"
                        "真空計と同じLANに接続して実行してください。")

    print(f"探索中: {subnet} / PC側IP: {source_ip}")

    packet = (Ether(dst = "ff:ff:ff:ff:ff:ff") / ARP(pdst = str(subnet), psrc = source_ip))

    answered, _ = srp(packet, iface = iface, timeout = 3, retry = 1, inter = 0.01, verbose = False,)

    matches = {reply[ARP].psrc for _, reply in answered if reply.haslayer(ARP) and reply[ARP].op == 2 and reply[ARP].hwsrc.lower() == target}

    if not matches:
        raise RuntimeError(f"MAC {mac} が見つかりません。"
            "電源・LAN接続・探索範囲・VLANを確認してください。")

    if len(matches) != 1:
        raise RuntimeError(f"同じMACに複数のIPが応答しました: {sorted(matches)}")

    return matches.pop()

IP = find_ip_by_mac(TARGET_MAC, NETWORK)
print(f"Prologixを発見: {IP}")

def send(sock, command):
    sock.sendall((command + "\n").encode("ascii"))

def query_lakeshore(sock, stream, command):
    send(sock, command)
    send(sock, "++read eoi")

    response = stream.readline(4096)
    if not response.endswith(b"\n"):
        raise ConnectionError(f"応答が不完全です: {response!r}")

    time.sleep(0.05)
    return response.decode("ascii").strip()

try:
    with socket.create_connection((IP, 1234), timeout = 5) as sock:
        with sock.makefile("rb") as stream:
            # Prologixの通信設定
            for command in (
                "++mode 1", # GPIBコントローラとして動作
                "++auto 0", # 読み取りは明示的に実行
                f"++addr {GPIB_ADDRESS}",
                "++eoi 1",
                "++eos 0", # 送信終端：CR/LF
                "++eot_enable 0",
                "++read_tmo_ms 2000",):
                send(sock, command)

            identity = query_lakeshore(sock, stream, "*IDN?")
            print("接続機器:", identity)

            status = int(query_lakeshore(sock, stream, "RDGST? 1"))
            if status != 0:
                print(f"CH1の測定状態を確認してください: status={status}")
            else:
                temperature = float(query_lakeshore(sock, stream, "KRDG? 1"))
                print(f"CH1: {temperature:.3f} K")

except (OSError, ValueError) as error:
    print(f"通信・読み取りエラー: {error}")
