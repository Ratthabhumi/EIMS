# 🏆 MASTER CLASS: HOMELAB CLOUD & SRE PLATFORM CHEATSHEET
> **คัมภีร์สรุประบบ Enterprise Zero-Trust HomeLab & Observability (ฉบับจบในแผ่นเดียว)**
> *สร้างและพัฒนาโดย: Ratthabhumi & Antigravity (Advanced Agentic AI)*

---

## 🏛️ 1. สัตยาธิษฐานแห่งสถาปัตยกรรม (Core Architectural Concept)
เราได้ทำการแปลงร่างเซิร์ฟเวอร์โน้ตบุ๊ก **Acer Aspire V13 (`mew@homelab`)** ให้กลายเป็นศูนย์บัญชาการ **Cloud-Native & Platform Engineering** ยุคใหม่ โดยออกแบบให้อยู่ภายใต้ปรัชญา:
1. **Lightweight & High Performance:** เลือกใช้ **Docker Containers** (แทน Virtual Machines) เพื่อประหยัด CPU/RAM ไว้รัน AI และ Services หนักๆ ได้สูงสุด
2. **GitOps Single-Source-of-Truth:** โค้ดทุกบรรทัดและคอนฟิกเซิร์ฟเวอร์ถูกเขียนและพัฒนาบนเครื่องทำงาน PC (VS Code) และซิงค์ขึ้น **GitHub** ก่อนจะถูกสั่งบูตที่เซิร์ฟเวอร์ผ่านระบบ GitOps 
3. **Zero-Trust Mesh Networking:** ใช้ **Tailscale Overlay Network** + **Traefik Edge Gateway** ปิดกั้นพอร์ตอันตราย และทะลุผ่าน Nat/Firewall ด้วยความปลอดภัยระดับองค์กร

---

## ⚙️ 2. คัมภีร์คำสั่งสั่งการหลัก (GitOps & Makefile Engine)
ในการอัปเดตหรือติดตั้งระบบใหม่ ให้ยึดกระบวนการ **"Golden GitOps Loop"** เสมอ:

### 🌟 2.1 คำสั่งบนฝั่งเครื่องคนทำงาน (Terminal ใน VS Code PC)
เมื่อคุณเขียนโค้ดหรือแก้ไขไฟล์คอนฟิกเสร็จแล้ว:
```powershell
# 1. เช็กสถานะไฟล์ที่ถูกปรับปรุง
git status

# 2. เตรียมแพ็คไฟล์ทั้งหมดเข้าคลัง
git add .

# 3. ประทับตราบันทึกข้อความอัปเดต (Commit Message)
git commit -m "⚡ รายละเอียดสิ่งที่คุณแก้ไขหรือเพิ่มเติม"

# 4. ดันโค้ดพุ่งทะยานขึ้นคลาวด์ GitHub
git push -u origin main
```

---

### 🌟 2.2 คำสั่งบนฝั่งเซิร์ฟเวอร์ (Terminal ในจอ SSH `mew@homelab`)
เมื่อล็อกインเข้าเซิร์ฟเวอร์แล้ว ให้เดินทางเข้าโฟลเดอร์หลักแล้วสั่งการด้วย **Makefile Engine**:

```bash
# 1. เดินทางเข้าโฟลเดอร์คลังศูนย์กลางโลก Homelab
cd ~/Pi_Personal-Infrastructure    # (หรือใช้คำสั่งลัด: cdlab)

# 2. ดึงอัปเดตโค้ดล่าสุดจากคลาวด์ GitHub มาสถิตที่โน้ตบุ๊ก
git pull origin main
```

| คำสั่ง Makefile สั่งการ | หน้าที่และความหมาย (What it does) |
| :--- | :--- |
| `make apply-local` | 🛡️ **Self-Bootstrapping:** ปลุกระบบ Ansible ตรวจเช็กและปรับจูนความปลอดภัย OS, โหลด Docker Engine และเปิด UFW Firewall อัตโนมัติ |
| `make core-up` | 🚀 **Start Core Stack:** เปิดใช้งานประตูเฝ้ายาม **Traefik (Reverse Proxy)** และศูนย์คุมระบบ **Portainer CE (Web UI)** |
| `make tf-apply` | ยืนยันการยิงโค้ด Terraform ขึ้นไปแก้ DNS ของจริง |

### 🤖 CI/CD Pipeline (Sprint 8)
| Command/Action | Description |
| :--- | :--- |
| `git push` | สั่งให้ GitHub Actions ตรวจสอบโค้ด (CI) และรัน Deploy (CD) อัตโนมัติ |
| `sudo ./svc.sh status` | เช็คสถานะหุ่นยนต์ Self-Hosted Runner ในเครื่องเซิร์ฟเวอร์ |
| `sudo ./svc.sh start/stop` | เปิด/ปิดการทำงานของหุ่นยนต์รับคำสั่งจาก GitHub |

### 📦 Utilities & SRE Toolstack
| คำสั่ง Makefile สั่งการ | หน้าที่และความหมาย (What it does) |
| :--- | :--- |
| `make obs-up` | 📊 **Start Observability Stack:** เปิดตู้เครื่องมือแพทย์ **VictoriaMetrics**, **Node Exporter**, **cAdvisor** และห้องบัญชาการ **Grafana** |
| `make autodox` | 📝 **Autonomous Documenter:** ปลุกหุ่นยนต์ Python สแกนสถานะทุก Container และอัปเดตไฟล์สถิติ [live_inventory.md](file:///c:/Users/MewMew/Desktop/Co-op/Pi_Personal-Infrastructure/docs/architecture/live_inventory.md) อัตโนมัติ |
| `make backup` | 🛡️ **Snapshot & Backup Engine:** แพ็กข้อมูล Volume สำคัญ (Grafana/Portainer) เป็น `.tar.gz` พร้อมลบไฟล์สถิติเก่าเกิน 7 วันออกอัตโนมัติ |
| `make status` | 🔍 **Health Inspector:** ตรวจดูชื่อ Container ทั้งหมดที่กำลังทำงาน พร้อมมาตรวัดกิน RAM/CPU แบบเรียลไทม์ |
| `make core-down` | 🛑 **Shutdown Core:** ปิดพักระบบ Traefik & Portainer อย่างนิ่มนวล (ข้อมูลไม่สูญหาย) |
| `make obs-down` | 🛑 **Shutdown Observability:** ปิดพักระบบ Grafana & VictoriaMetrics อย่างนิ่มนวล (ข้อมูลไม่สูญหาย) |

---

## 🔥 3. คำสั่งลัดประจำมือวิศวกร (Bash Super Aliases)
เพื่อลดเวลาพิมพ์ยาวๆ ระบบได้รับการเสกคาถาคำสั่งลัดฝังไว้ใน `.bashrc` ของเครื่อง Ubuntu แล้ว:
* **`cdlab`**  👉 กระโดดวาร์ปเข้าโฟลเดอร์ `~/Pi_Personal-Infrastructure` ทันทีจากทุกที่ในระบบ!
* **`dps`**    👉 แสดงรายชื่อ Docker Containers ที่รันอยู่ด้วยกราฟิกและสีที่สะอาดตา ดูง่ายกว่า `docker ps` ทั่วไป 10 เท่า
* **`dlog <ชื่อตู้>`** 👉 ดูคลื่นบันทึกการทำงาน (Logs) แบบเรียลไทม์ของตู้ที่ต้องการ เช่น `dlog victoriametrics` หรือ `dlog traefik`
* **`dstop <ชื่อตู้>`** 👉 ปิดและถอดถอน Container ที่เกิดอาการค้างออกจากระบบอย่างฉับไว

---

## 🌐 4. ตารางพิกัดเข้าใช้งานระบบผ่านหน้าเว็บ (Web UI Matrix)
คุณสามารถเปิดโปรแกรมเว็บเบราว์เซอร์บนเครื่อง Dell Windows Workstation หรืออุปกรณ์ในเครือข่าย Tailscale เพื่อเข้าใช้งานระบบได้ทันที:

| บริการ (Service) | พอร์ต / ลิงก์เข้าเว็บ | หน้าที่รับผิดชอบ | ข้อมูลล็อกอินเริ่มต้น (Credentials) |
| :--- | :--- | :--- | :--- |
| **Portainer CE** | `https://homelab:9443`<br>*(หรือ `https://100.116.167.3:9443`)* | แผงควบคุมกดคลอด ตรวจสอบ และสั่งการ Docker Container ผ่านปุ่มบนเว็บ โดยไม่ต้องพิมพ์คำสั่ง | *ตั้งค่ารหัสผ่านใหม่เองในการเข้าใช้งานครั้งแรก* |
| **Grafana** | `http://homelab:3000`<br>*(หรือ `http://100.116.167.3:3000`)* | ห้องบัญชาการจอภาพ Mission Control สไตล์ NASA/Cyberpunk แปลงตัวเลขเป็นกราฟิกสวยหรู 24 ชั่วโมง | **User:** `admin`<br>**Pass:** `admin123` *(ระบบจะให้ตั้งใหม่)* |
| **VictoriaMetrics** | `http://100.116.167.3:8428` | เครื่องยนต์ Time-Series Database ที่เก็บข้อมูลชีพจร (เร็วกว่า และประหยัดแรมกว่า Prometheus 5 เท่า!) | - |
| **Traefik** | `http://100.116.167.3:80`<br>`https://100.116.167.3:443` | ตำรวจจราจรผู้แจกแจง Domain name และ SSL Certificate ให้ทุกแอปในบ้าน (Edge Ingress Gateway) | - |
| **AdGuard Home** | `http://adguard.homelab.lan`<br>`http://100.116.167.3:8081` | ศูนย์ควบคุม DNS และหลุมดำดูดโฆษณา (Ad-blocker) สำหรับทุกอุปกรณ์ในบ้าน | *ตั้งค่ารหัสผ่านใหม่ในการเข้าใช้งานครั้งแรก* |
| **Vaultwarden** | `https://vaultwarden.homelab.ts.net` | ตู้เซฟรหัสผ่านส่วนตัวสุดปลอดภัย (ต้องเข้าผ่าน HTTPS เสมอ เพื่อให้ระบบเข้ารหัสทำงานได้) | *ตั้งค่ารหัสผ่านใหม่ในการเข้าใช้งานครั้งแรก* |
| **Uptime Kuma** | `http://kuma.homelab.lan` | ยามเฝ้าระวังเซิร์ฟเวอร์ คอยแจ้งเตือนผ่าน Telegram/Discord ทันทีถ้าระบบหรือเน็ตเวิร์กล่ม | *ตั้งค่ารหัสผ่านใหม่ในการเข้าใช้งานครั้งแรก* |

---

## 🔮 5. กลเม็ดรหัสวิเศษเสกกัปตัน SRE (Grafana Magic Dashboards)
ในหน้าจอเว็บ **Grafana (`http://homelab:3000`)** คุณไม่ต้องปวดหัวนั่งสร้างกราฟเอง ให้ทำตามขั้นตอนนี้เพื่อโหลดกราฟระดับโลก:
1. คลิกเมนูซ้ายมือ **`Dashboards`** -> คลิกปุ่ม **`New`** มุมขวาบน -> เลือก **`Import`**
2. กรอกตัวเลข **Magic ID** ลงในช่อง *Import via grafana.com* -> กดปุ่ม **`Load`**
3. ด้านล่างสุดเลือกพอยต์ไปที่ **`VictoriaMetrics`** (ซึ่งถูกเชื่อมต่อสายไว้อัตโนมัติแล้ว) -> กด **`Import`**

### 🎯 รายชื่อ Magic ID สุดแกร่งที่ควรติดห้องไว้:
* 🌟 **ID: `1860` (Node Exporter Full):** ปรอทวัดไข้ฮาร์ดแวร์เซิร์ฟเวอร์ตัวจริง เสียงจริง! แสดงความร้อน CPU, เปอร์เซ็นต์ใช้ RAM, ความเร็วอ่านเขียนฮาร์ดแวร์ และสถิติเน็ตเวิร์ก
* 🌟 **ID: `14282` (Docker Containers Vitals):** เจาะลึกชีพจรของทุก Docker Container ที่รันอยู่ในบ้านว่าตู้ไหน (เช่น AI / Traefik / Portainer) แอบกินสเปคเครื่องอยู่เท่าไหร่!

> [!TIP]
> **เคล็ดลับกับดักเวลา (Time Range Trap):** หากเปิดกราฟเข้ามาแล้วพบว่าตัวเลขขึ้น `N/A` หรือ `No data` **ไม่ต้องตกใจ!** นั่นเพราะระบบเพิ่งรันได้ไม่กี่นาที แต่ Grafana ตั้งค่าเบื้องต้นให้แสดงผลย้อนหลัง 24 ชั่วโมง (`Last 24 hours`)  
> **วิธีแก้:** ให้คลิกเปลี่ยนสเกลเวลาที่มุมขวาบนสุดจาก `Last 24 hours` เปลี่ยนเป็น 👉 **`Last 5 minutes`** หรือ **`Last 15 minutes`** กราฟทุกช่องจะพุ่งขึ้นมาทันที!

---

## 🛠️ 6. คู่มือแก้ไขปัญหาฉับพลันสไตล์วิศวกร SRE (Troubleshooting & Diagnostics)

### 🚨 ปัญหา 1: หน้าเว็บ Grafana ขึ้นแถบสีแดงด่าว่า *"An error occurred within the plugin"* หรือ *"dial tcp: lookup victoriametrics on 127.0.0.11"*
* **สาเหตุที่แท้จริง (Root Cause):** ตู้เซิร์ฟเวอร์เก็บชีพจรหลังบ้าน (`victoriametrics`) เปิดไม่ขึ้นหรือสลบไป ทำให้ระบบเบอร์โทรภายในของ Docker (Internal DNS) ปฏิเสธการเชื่อมต่อจาก Grafana
* **วิธีสกัดจับและซ่อมบำรุง:**
  1. ในหน้าจอ SSH พิมพ์ `dps` เพื่อดูว่ามีรายชื่อตู้ `victoriametrics` หรือไม่
  2. พิมพ์ `dlog victoriametrics` เพื่ออ่านบรรทัดสุดท้าย (Fatal Logs) จะรู้ทันทีว่าพังเพราะคอนฟิกพิมพ์ผิด หรือติดปัญหาอะไร
  3. เมื่อแก้โค้ดในคอม PC แล้ว สั่งดึงอัปเดตและบูตใหม่ด้วย:
     ```bash
     cd ~/Pi_Personal-Infrastructure && git pull && make obs-up
     ```

### 🚨 ปัญหา 2: ในหน้า SSH พิมพ์คำว่า make แล้วระบบด่าว่า *Command 'make' not found*
* **สาเหตุและวิธีแก้:** เกิดขึ้นในเครื่อง Ubuntu ที่เพิ่งลงระบบใหม่ สามารถสั่งติดตั้งชุดเครื่องมือ Compile ได้ด้วยคำสั่งเดียว:
  ```bash
  sudo apt update && sudo apt install -y make
  ```

### 🚨 ปัญหา 3: อยากเข้าดูว่า Container ในบ้านคุยกันรู้เรื่องไหม (Network Ping Diagnostic)
* สามารถสั่งใช้สคริปต์ Docker เช็คสถานะหรือ Ping หากันในเครือข่ายวงแลนเสงี่ยม `homelab_mesh` ได้ตลอดเวลา:
  ```bash
  # ดูรายชื่อวงแลน Docker ในบ้านทั้งหมด
  docker network ls
  ```

### 🚨 ปัญหา 4: Docker ฟ้องว่า "client version 1.24 is too old"
* **สาเหตุ:** Container (เช่น `cadvisor`, `traefik`) ใช้ API รุ่นเก่าเพื่อคุยกับ Docker Socket แต่ Ubuntu 24.04 ติดตั้ง Docker Engine v26+ ซึ่งยกเลิกรองรับ API รุ่นเก่าแล้ว
* **วิธีแก้:** ต้องบังคับให้ Container ใช้ API รุ่นใหม่ โดยเพิ่ม Environment Variable ลงไปใน `compose.yaml` ของ Container ตัวนั้นๆ:
  ```yaml
  environment:
    - DOCKER_API_VERSION=1.44
  ```

### 🚨 ปัญหา 5: เข้าเว็บ Subdomain (เช่น grafana.homelab.ts.net) บน iPhone/มือถือ ไม่ได้
* **สาเหตุ:** Tailscale MagicDNS จะแปลงชื่อเครื่องหลัก (เช่น `homelab`) เป็น IP ให้อัตโนมัติ แต่มัน **ไม่รองรับ Subdomain** (เช่น `grafana.`) บนอุปกรณ์มือถือ (iOS/Android) ทำให้หาปลายทางไม่เจอ
* **วิธีแก้เฉพาะหน้า (Fallback):** เปิดพอร์ตตรง (Port Forwarding) ทะลุออกมาในไฟล์ `compose.yaml` เพื่อให้เข้าผ่าน IP หรือชื่อเครื่องได้เลยโดยไม่ผ่าน Traefik Ingress:
  ```yaml
  grafana:
    ports:
      - "3000:3000"
  ```
  จากนั้นเข้าผ่าน URL 👉 `http://homelab:3000` หรือ `http://<Tailscale_IP>:3000`

---

## 💾 7. วิชาลับจัดการ Storage & Production Infrastructure (Sprint 4-5)

### 🚨 การย้าย Docker Data ลง HDD (Production Migration)
เพื่อถนอม SSD และใช้พื้นที่ HDD 1TB ให้คุ้มค่า เราทำการย้ายข้อมูลทั้งหมดไปที่ `/data`:
```bash
# 1. สร้างโฟลเดอร์ปลายทาง
sudo mkdir -p /data/docker/{traefik,portainer,grafana,victoriametrics}
sudo chown -R mew:mew /data/docker

# 2. คัดลอกข้อมูลแบบเซียน (เก็บ Permission ครบ)
rsync -a ~/Pi_Personal-Infrastructure/docker/core/portainer-data/ /data/docker/portainer/data/

# 3. รันระบบใหม่ด้วย Compose ไฟล์เดียว (Monolithic Compose)
cd /data/docker
docker compose up -d
```

### 🚨 การเขียน UUID อัตโนมัติ (Fstab Auto-Mount)
ฮาร์ดดิสก์จะไม่หลุดแม้รีบูตเครื่อง หรือแม้แต่สลับสายจาก USB ไปเป็น SATA เพราะเราผูกด้วยรหัสบัตรประชาชนฮาร์ดดิสก์ (UUID):
```bash
# ดูรหัส UUID ของทุกไดรฟ์
blkid

# เปิดไฟล์ fstab เพื่อฝังรหัส (ระวังพังถ้าเขียนผิด!)
sudo nano /etc/fstab
# ตัวอย่างการเขียน: UUID=xxxx-xxxx /data ext4 defaults 0 2
```

### 🚨 เคลียร์ซากอารยธรรม (Docker Purge)
หากระบบเก่าพัง หรือ IP Network ชนกัน (Pool overlaps) ให้ใช้ท่าไม้ตายล้างบาง:
```bash
# ลบ Container ที่ค้างอยู่ทั้งหมด (แบบบังคับ)
docker rm -f $(docker ps -aq) 2>/dev/null

# ล้าง Network ที่ไม่ได้ใช้ทั้งหมดเพื่อคืน IP
docker network prune -f
```

### 🚨 แก้ Error: "client version 1.24 is too old" 
อาการนี้เกิดจาก Docker Daemon รุ่นใหม่ๆ (v27+) ยกเลิกการรองรับ API เวอร์ชันเก่า แต่มี Container บางตัว (เช่น cAdvisor หรือโปรแกรมรุ่นเก่า) พยายามสื่อสารด้วย API v1.24 
**วิธีแก้:** บังคับให้ Container ตัวนั้นใช้ API ใหม่โดยการเพิ่ม Environment Variable ใน `compose.yaml`:
```yaml
    environment:
      - DOCKER_API_VERSION=1.44
```

### 🚨 ปัญหาการเข้า Subdomain ผ่าน Tailscale บนมือถือ (DNS Resolution Failed)
Tailscale MagicDNS **ไม่รองรับ** การแปลผล Subdomain อัตโนมัติ (มันรู้จักแค่ชื่อ Host เครื่องหลัก เช่น `homelab` หรือ IP 100.x.x.x) 
หากคุณเข้า `grafana.homelab.ts.net` ผ่านมือถือ เบราว์เซอร์จะหาไม่เจอ 
**วิธีแก้ (สำหรับ HomeLab เบื้องต้น):** 
ให้ทำการ Expose Port ออกมาตรงๆ ใน `compose.yaml` (เช่นเพิ่ม `ports: - "3000:3000"`) แล้วเข้าผ่าน `http://homelab:3000` แทน 
(ปลอดภัย 100% เพราะ UFW Firewall บล็อคการเข้าถึงทั้งหมด ยกเว้นจากวง Tailscale `tailscale0` เท่านั้น)

---

## 🔔 8. คู่มือระบบแจ้งเตือนฉุกเฉิน (Alerting & Heartbeat)
เพื่อให้เซิร์ฟเวอร์รายงานตัวและแจ้งเตือนคุณแบบ Real-time เราใช้เทคนิคผสมผสาน (Hybrid Monitoring):

1. **Uptime Kuma (เฝ้ายามวงใน):**
   * ทะลวงเช็คชีพจรแอปทุกตัวจากในวงแลน Docker โดยเรียกชื่อตรงๆ (เช่น `http://vaultwarden:80`, `http://portainer:9000`)
   * หากแอปใดแอปหนึ่งค้าง จะส่งข้อความแจ้งเตือนผ่าน **Telegram Bot** ทันทีแบบวินาทีต่อวินาที
2. **Healthchecks.io (เฝ้ายามวงนอก):**
   * ใช้เทคนิค "Push Heartbeat" ให้ Uptime Kuma ยิงสัญญาณลับไปรายงานตัวกับเว็บทุกๆ 1 นาที
   * หากเซิร์ฟเวอร์ไฟดับ หรือเน็ตล่มตายไปทั้งเครื่องเกิน 10 นาที (สัญญาณหายไป) เว็บคนนอกจะส่ง **อีเมล** แจ้งเตือนฉุกเฉิน

---
*🚀 **Keep Building, Keep Escalating, and Never Stop Learning!** 🚀*
