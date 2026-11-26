# Topstep Fire Drill Watcher

Theo dõi `https://www.topstep.com/fire-drill` mỗi 10 phút và gửi **email** khi trang
thay đổi nội dung — tức là khi Topstep đăng fire drill / giveaway mới.

## Cách nó hoạt động

1. Tải HTML trang, bóc hết tag, chuẩn hoá text.
2. **Bỏ các con số biến động** (bộ đếm payout `$12,345,678`, countdown `00:45:00`)
   → không báo động giả mỗi lần counter nhảy số.
3. Hash phần text còn lại, so với lần chạy trước (lưu ở `state.json`).
4. Gửi email khi:
   - `[!!!]` **Câu "Missed your shot" biến mất** — đây là câu chỉ xuất hiện khi drill đã
     kết thúc. Mất câu này = rất có thể đang có drill mới mở. Đây là tín hiệu mạnh nhất.
   - `[*]` Hash đổi — trang có sửa nội dung bất kỳ.
   Email kèm sẵn phần diff cho biết dòng nào đã đổi.

Zero dependency — chỉ dùng thư viện chuẩn của Python.

## Cài đặt (khoảng 10 phút)

### 1. Tạo App Password cho Gmail

Gmail không cho đăng nhập SMTP bằng mật khẩu thường, phải dùng App Password:

1. Bật 2-Step Verification: https://myaccount.google.com/signinoptions/two-step-verification
2. Vào https://myaccount.google.com/apppasswords
3. Đặt tên bất kỳ (ví dụ `firedrill`) → Create → copy đoạn 16 ký tự.

### 2. Tạo repo và push code

```bash
cd topstep-firedrill-watcher
git init
git add .
git commit -m "Topstep fire drill watcher"
gh repo create topstep-firedrill-watcher --public --source=. --push
```

> **Nên để public.** GitHub Actions miễn phí không giới hạn phút với repo public.
> Repo private cũng chạy được: với lịch hiện tại (~1.300 lần/tháng) vẫn nằm trong
> hạn mức 2.000 phút/tháng của gói free, nhưng không còn nhiều dư.
> Code không chứa gì riêng tư — mật khẩu nằm trong GitHub Secrets, repo public
> cũng không đọc được.

### 3. Khai báo Secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Tên | Giá trị |
|---|---|
| `GMAIL_USER` | địa chỉ Gmail của anh |
| `GMAIL_APP_PASSWORD` | App Password 16 ký tự ở bước 1 (bỏ khoảng trắng) |
| `MAIL_TO` | email nhận thông báo (bỏ trống thì gửi về chính `GMAIL_USER`) |

Tuỳ chọn, nếu sau này muốn thêm Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
Script tự bỏ qua nếu không khai báo.

### 4. Chạy thử

Repo → tab **Actions** → `Topstep Fire Drill Watcher` → **Run workflow**.

- Lần chạy đầu chỉ lưu baseline, **không** gửi email (đúng như thiết kế).
- Muốn kiểm tra email có thông được: sửa `DORMANT_MARKERS` trong `watcher.py`
  thành một câu không tồn tại trên trang, chạy tay 1 lần → phải nhận được email,
  rồi sửa lại.

## Lịch chạy

```
*/10 13-22 * * 1-5     # UTC
```

= mỗi 10 phút, **20:00 – 05:59 giờ Việt Nam**, thứ 2 đến thứ 6 — khớp giờ TopstepTV
phát sóng theo giờ Mỹ. Muốn chạy 24/7 thì đổi thành `*/10 * * * *`.

## Vài điều cần biết

- **Cron của GitHub không đúng giờ tuyệt đối**, thường trễ 5–15 phút, lúc cao điểm có
  thể hơn. Với fire drill chạy vài chục phút thì vẫn kịp, nhưng đừng coi đây là
  realtime. Muốn chắc hơn thì giảm xuống `*/5`.
- GitHub **tự tắt** scheduled workflow sau 60 ngày repo không có hoạt động nào. Anh sẽ
  nhận email cảnh báo trước khi bị tắt — lúc đó chỉ cần vào bấm enable lại.
- Nếu Topstep đổi sang render bằng JavaScript hoặc bật chặn bot (Cloudflare), script sẽ
  fail → GitHub tự gửi email báo workflow lỗi, nên anh vẫn biết là nó hỏng chứ không
  im lặng.
- Trang này **không** có lịch drill. Chỉ khi nào drill mở thì nội dung mới đổi — nên đây
  là cách duy nhất biết sớm ngoài việc ngồi xem TopstepTV.
