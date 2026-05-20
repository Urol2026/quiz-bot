# 🤖 Telegram Quiz Bot — Lexicology (521 savol)

## 📁 Kerakli fayllar
```
bot.py            ← Bot asosiy kodi
questions.json    ← 521 ta savol (avtomatik yaratilgan)
requirements.txt  ← Kutubxonalar
```

## 🚀 Ishga tushirish (3 qadam)

### 1. Token olish
1. Telegramda [@BotFather](https://t.me/BotFather) ga yozing
2. `/newbot` buyrug'ini yuboring
3. Bot nomi va username bering (masalan: `LexicologyQuizBot`)
4. BotFather sizga token beradi: `1234567890:ABCdef...`

### 2. bot.py faylida tokenni o'zgartiring
```python
BOT_TOKEN = "1234567890:ABCdef..."   # ← shu yerga o'z tokeningizni yozing
```

### 3. Ishga tushirish
```bash
# Kutubxonalarni o'rnatish
pip install python-telegram-bot==20.7

# Botni ishga tushirish
python bot.py
```

---

## ⚙️ Sozlamalar (bot.py ichida)
| Sozlama | Qiymat | Tavsif |
|---------|--------|--------|
| `QUIZ_LENGTH` | `10` | Har sessiyada nechta savol |
| `BOT_TOKEN` | `"..."` | BotFather dan olingan token |

## 🎮 Bot buyruqlari
| Buyruq | Vazifasi |
|--------|----------|
| `/start` | Botni boshlash / bosh menyu |

## 📊 Funksiyalar
- ✅ 521 ta tasodifiy savol
- 🔀 Har o'yinda boshqa 10 ta savol
- 📋 A/B/C/D variantlar (aralashtirilib beriladi)
- ✅ To'g'ri javob tushuntirishi
- 🏆 Liderlar jadvali (TOP 10)
- 📊 Shaxsiy statistika (o'yinlar, eng yaxshi ball, o'rtacha)
- 🎯 Ball va foiz ko'rsatish

## ☁️ Server (ixtiyoriy)
Agar bot 24/7 ishlashi kerak bo'lsa:
- **Railway.app** (bepul)
- **Render.com** (bepul)
- **VPS** (DigitalOcean, Hetzner)

```bash
# Background ishlatish (Linux)
nohup python bot.py &
```
