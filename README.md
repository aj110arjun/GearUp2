# 🛠️ GearUp

**GearUp** is a full-featured e-commerce web application built with **Django**, designed for selling **survival gear and accessories**.  
It includes a **custom admin panel**, **product variant management**, and **time-based OTP authentication** for secure sign-up.

---

## 🚀 Features

- 🔐 **User Authentication**
  - Secure login and sign-up with **TOTP (Time-based OTP)** using `django-otp`
- 🧾 **Custom Admin Dashboard**
  - Manage categories, products, variants, and offers
- 🛍️ **Product Management**
  - Add multiple product images and variants (size, color, etc.)
- 💸 **Offers & Discounts**
  - Category-based and product-based offer system with validation
- 💰 **Wallet & Refund**
  - Refunds processed directly to user wallets on order cancellations
- 🧮 **Order & Cart System**
  - Add to cart, checkout, and track orders


---

## 🧩 Tech Stack

| Component | Technology |
|------------|-------------|
| Backend | Django (Python) |
| Frontend | HTML, CSS, Bootstrap |
| Database | PostgreSQL / SQLite |
| Authentication | Django-OTP |
| Deployment | Gunicorn + Nginx |

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the repository
```bash
git clone https://github.com/aj110arjun/GearUp2.git
cd gearup


