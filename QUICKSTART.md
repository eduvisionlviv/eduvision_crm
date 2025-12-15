# 🚀 EduVision CRM - Quick Start Guide

## 5-Minute Setup

### Step 1: Database Setup (2 minutes)

1. **Open Supabase SQL Editor**
   - Go to your Supabase project
   - Click on "SQL Editor"

2. **Run Migration Scripts**
   ```sql
   -- Copy and paste the contents of:
   db_migrations/01_create_crm_tables.sql;
   db_migrations/02_bank_accounts.sql;  -- додає шифроване сховище банківських реквізитів
   ```

3. **Click "Run"** to create all tables

✅ Your database is ready!

---

### Step 2: Environment Variables (1 minute)

Create a `.env` file or set these environment variables:

```bash
# Supabase Configuration
SUPABASE_URL1=your_main_database_url
HDD=your_main_database_service_role_key
SUPABASE_URL2=your_stock_database_url
HDD2=your_stock_database_service_role_key

# Authentication
AUTH_TTL_HOURS=168          # 7 days session
COOKIE_SECURE=1             # Use secure cookies
BANK_ENCRYPTION_KEY=base64:your32bytefernetkey

# Recovery Options
USE_TG_RECOVERY=1           # Enable Telegram recovery
USE_EMAIL_RECOVERY=1        # Enable email recovery

# App URL (for emails and links)
PUBLIC_APP_URL=http://localhost:8080
```

✅ Configuration complete!

---

### Step 3: Install Dependencies (1 minute)

```bash
pip install -r requirements.txt
```

Dependencies include:
- Flask (web framework)
- Supabase (database client)
- bcrypt (password hashing)
- Flask-CORS (cross-origin support)

✅ Dependencies installed!

---

### Step 4: Start the Server (30 seconds)

```bash
python main.py
```

You should see:
```
🚀 Chromium launched (if PDF generation is needed)
🛎️ Browser idle monitor started
INFO:werkzeug: * Running on http://0.0.0.0:8080
```

✅ Server is running!

---

### Step 5: First Login (30 seconds)

1. **Open browser**: `http://localhost:8080`

2. **Register a test admin**:
   - Click "Реєстрація"
   - Fill in:
     - Name: Test Admin
     - Email: admin@test.com
     - Phone: +380501234567
     - Password: test123

3. **Approve in database** (for testing):
   ```sql
   -- In Supabase, move from register to contacts
   INSERT INTO contacts (user_email, user_name, user_phone, pass_email, user_access)
   SELECT user_email, user_name, user_phone, pass_email, 'def'
   FROM register WHERE user_email = 'admin@test.com';
   
   DELETE FROM register WHERE user_email = 'admin@test.com';
   ```

4. **Login**:
   - Email: admin@test.com
   - Password: test123

 5. **Choose role**: "Я працівник"

✅ You're in the admin dashboard!

## Що вже вміє система (простими словами)

- **Облік навчання**: курси, групи, уроки, відвідуваність та платежі для учнів і батьків.
- **Адмін-ролі**: адміністратор, менеджер навчального центру, викладач, студент та батько/мати.
- **Телеграм-помічник**: бот відповідає на /start, прив'язує номер телефону для відновлення доступу і швидко реагує на втрати зв'язку.
- **Поштовий доступ**: скидання паролю через email та «плавний» перехід від відкритого пароля до bcrypt після першого входу.
- **Інтеграції з банками**: зберігаємо зашифровані API-ключі та номери рахунків (ПриватБанк, Monobank) у Supabase; реквізити можна завантажити через адмінку/API.
- **PDF/Browser утиліти**: вбудований Playwright для друку договорів і рахунків (за потреби).

Прості зв'язки:
- Supabase зберігає основні таблиці (контакти, уроки, оплати) та нову `crm_bank_accounts` з шифрованими ключами банку.
- Flask API обслуговує веб-адмінку, приймає банківські реквізити й передає їх інтеграціям.
- Telegram-бот працює у фоні, викликає бекенд через `/api/tg/link_recovery` і допомагає підтвердити користувача.
- Frontend (папка `web/`) працює поверх того ж Flask і використовує cookie `edu_session` для доступу до API.

### Готовий тестовий логін (плавний перехід)

Якщо треба швидко увійти без реєстрації:

- Email: `gammmerx@gmail.com`
- Пароль: `gfhfif32`

Пароль вперше записується у таблицю відкритим текстом, щоб підтримати легасі-акаунти. Після першого успішного входу бекенд автоматично перехешує його в bcrypt і оновлює `pass_email`, тож наступні входи будуть через хешований пароль.

---

## 🔧 Усунення проблем входу та Telegram (українською)

- **Не вдається увійти?**
  1. Перевірте, що бекенд працює: відкрийте `http://localhost:8080/ping` — має повернути `{ "status": "ok" }`.
  2. Переконайтесь, що у браузері збережено cookie `edu_session` після логіну. Якщо немає, вимкніть блокувальники 3rd-party cookies або встановіть `COOKIE_SECURE=0` для локального http.
  3. Якщо обліковий запис створювався через таблицю `register`, переконайтесь, що запис перенесено в `contacts/parents/student` та там є поле `pass_email` із bcrypt-хешем.
  4. Для локальних тестів можна видати сесію вручну: у таблиці користувача заповніть `auth_tokens` унікальним рядком і `expires_at` часом у майбутньому (ISO, UTC).

- **Telegram-бот не працює?**
  1. Перевірте налаштування: `curl http://localhost:8080/api/tg/status` поверне `configured: true` та `bot_username`, якщо токен коректний.
  2. Додайте `TELEGRAM_BOT_TOKEN=<токен від BotFather>` (працюють також `BOT_TOKEN`, `TELEGRAM_TOKEN`, `TELEGRAM_API_TOKEN`); за потреби вкажіть `TELEGRAM_PROXY=<http(s)://user:pass@host:port>` у змінні середовища. Без токена бот не стартує.
  3. Для Kubernetes/Docker secret можна передати шлях до файлу з токеном через `TELEGRAM_BOT_TOKEN_FILE` (або `BOT_TOKEN_FILE`, `TELEGRAM_TOKEN_FILE`), а `.env` у корені проєкту завантажується автоматично при старті.
  4. Якщо `/api/tg/status` показує `status: error`, токен може бути невірним або мережа блокує доступ до api.telegram.org. Додайте `TELEGRAM_API_BASE=https://<ваш-endpoint>` (наприклад, локальний проксі з DNS-доступом) і, за потреби, `TELEGRAM_PROXY=...`, щоб обійти проблеми з резолвом чи TLS-інспекцією. Бот сам перепідключається з паузою 10 секунд і чистить «завислі» апдейти.
  5. Для прив'язки Telegram до акаунта надішліть собі лист через кнопку «Надіслати лист» у профілі, відкрийте бота за посиланням і поділіться номером телефону.

---

## 🎯 What to Try First

### Add Your First Course
1. Click "Курси" in sidebar
2. Click "➕ Додати курс"
3. Fill in:
   - Name: "English A1"
   - Duration: 6 months
   - Age: 7-10 years
   - Price: 1500
4. Click "Зберегти"

### Create Your First Group
1. Click "Групи" in sidebar
2. Click "➕ Створити групу"
3. Fill in:
   - Name: "English A1 - Group 1"
   - Course: Select "English A1"
   - Max students: 10
   - Room: "101"
4. Click "Зберегти"

### Add a Student (Manual DB Entry)
```sql
-- Add to student table
INSERT INTO student (user_email, user_name, user_phone, pass_email, user_access)
VALUES ('student@test.com', 'John Doe', '+380501234568', 
        '$2b$12$...bcrypt_hash...', 'student');
```

Then enroll them in your group through the Groups page!

---

## 📱 Testing Responsive Design

### Desktop View (> 1024px)
- Sidebar navigation on the left
- 3-4 column grid layouts
- Full tables with all columns

### Tablet View (768px - 1024px)
- Sidebar hidden
- Bottom navigation appears
- 2-column grid layouts

### Mobile View (< 768px)
- Bottom navigation
- Single column layouts
- Simplified tables
- Touch-friendly buttons

**Test it**: Resize your browser window or use Chrome DevTools!

---

## 🔐 Testing Multiple Roles

### Create a Teacher Account
```sql
INSERT INTO contacts (user_email, user_name, user_phone, pass_email, user_access)
VALUES ('teacher@test.com', 'Jane Teacher', '+380501234569',
        -- hash for 'test123'
        '$2b$12$KIX8pGWKl8fWHr3qJKPMQu3xE5YQ9k.EXAMPLE',
        'teacher');
```

### Create a Parent Account
```sql
INSERT INTO parents (user_email, user_name, user_phone, pass_email, user_access)
VALUES ('parent@test.com', 'Mary Parent', '+380501234570',
        '$2b$12$KIX8pGWKl8fWHr3qJKPMQu3xE5YQ9k.EXAMPLE',
        'parent');
```

### Test Multi-Profile Login
Create an account with both teacher AND parent access:
```sql
-- Add to contacts as teacher
INSERT INTO contacts (user_email, user_name, user_phone, pass_email, user_access)
VALUES ('both@test.com', 'Bob Both', '+380501234571',
        '$2b$12$KIX8pGWKl8fWHr3qJKPMQu3xE5YQ9k.EXAMPLE',
        'teacher');

-- Add to parents with SAME email
INSERT INTO parents (user_email, user_name, user_phone, pass_email, user_access)
VALUES ('both@test.com', 'Bob Both', '+380501234571',
        '$2b$12$KIX8pGWKl8fWHr3qJKPMQu3xE5YQ9k.EXAMPLE',
        'parent');
```

Now login with `both@test.com` and you'll see **role selection**!

---

## 🐛 Troubleshooting

### Issue: Can't connect to database
**Solution**: Check your Supabase URLs and keys in `.env`

### Issue: Login fails
**Solution**: 
1. Verify user exists in database
2. Check password hash is correct
3. Look at browser console for errors

### Issue: Styles not loading
**Solution**: 
1. Clear browser cache (Ctrl+Shift+R)
2. Check `/css/styles.css` loads in Network tab
3. Verify path in HTML: `<link rel="stylesheet" href="/css/styles.css">`

### Issue: API returns 401 Unauthorized
**Solution**: You're not logged in. Go to `/` and login first.

### Issue: Tables are empty
**Solution**: 
1. Add data through the UI (courses, groups)
2. Or insert test data directly in Supabase

### Issue: JavaScript errors in console
**Solution**: 
1. Check `/js/app.js` loads correctly
2. Verify user session with `/api/login/me`
3. Open browser console (F12) for details

---

## 📚 Next Steps

### For Admins
1. ✅ Add all your courses
2. ✅ Create groups for each course
3. ✅ Add teachers to database
4. ✅ Assign teachers to groups
5. ✅ Import student data
6. ✅ Enroll students in groups

### For Developers
1. 📖 Read `CRM_IMPLEMENTATION.md` for technical details
2. 🔍 Explore the API endpoints
3. 🎨 Customize the CSS variables in `styles.css`
4. 🔧 Add new features from TODO list
5. 📊 Build reports and analytics

### For Production
1. ⚙️ Set `COOKIE_SECURE=1` and use HTTPS
2. 🔒 Change all default passwords
3. 📧 Configure email service (Gmail)
4. 💬 Setup Telegram bot (optional)
5. 📊 Enable monitoring and logging
6. 💾 Setup automated backups
7. 🧪 Test with real user scenarios

---

## 🎉 You're All Set!

Your EduVision CRM is now running and ready to use!

**Need help?** 
- Check `CRM_IMPLEMENTATION.md` for detailed docs
- Check `IMPLEMENTATION_SUMMARY.md` for overview
- Open an issue on GitHub

**Enjoy your new CRM system! 🎓**

---

*Happy managing! 📚*
