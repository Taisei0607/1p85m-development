import socket
import time
from datetime import datetime
import ipaddress
from scapy.all import ARP, Ether, conf, srp

TARGET_MAC = "00:A0:41:0A:67:01"
NETWORK = "192.168.0.0/24"

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
print(f"TPG 361を発見: {IP}")

PORT = 8000

def read_line(stream):
    data = stream.readline(256)
    if not data.endswith(b"\r\n"):
        raise ConnectionError(f"応答が不完全です: {data!r}")
    return data[:-2]

def query(sock, stream, command):
    sock.sendall(command.encode("ascii") + b"\r")

    for _ in range(20):
        reply = read_line(stream)
        if reply == b"\x06": # ACK
            break
        if reply == b"\x15": # NAK
            raise RuntimeError(f"コマンドが拒否されました: {command}")
    else:
        raise RuntimeError("ACKを確認できませんでした")

    sock.sendall(b"\x05") # ENQ
    return read_line(stream).decode("ascii").strip()

try:
    with socket.create_connection((IP, PORT), timeout = 3) as sock:
        with sock.makefile("rb") as stream:
            while True:
                unit = query(sock, stream, "UNI")
                if unit != "1": # 1 = Torr
                    raise RuntimeError(f"単位設定がTorrではありません（UNI={unit}）")

                response = query(sock, stream, "PR1")
                status, value = response.split(",", 1)
                status = int(status)
                now = datetime.now().isoformat(timespec = "seconds")

                if status == 0:
                    pressure = float(value)
                    print(f"{now} {pressure:.4e} Torr", flush = True)
                else:
                    print(f"{now} 測定値無効: status = {status}, "
                        f"応答 = {response}", flush = True,)

                time.sleep(1)

except KeyboardInterrupt:
    print("終了しました")
except (OSError, ValueError, RuntimeError) as error:
    print(f"取得停止: {error}")
