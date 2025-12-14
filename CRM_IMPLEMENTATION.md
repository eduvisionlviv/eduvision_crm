# EduVision CRM - Документація реалізації

## Огляд системи

EduVision CRM - це повноцінна система управління навчальним центром з інтуїтивним мінімалістичним дизайном та адаптивною версткою для всіх пристроїв.

## Архітектура

### Backend (Python/Flask)

**API Endpoints:**

- `/api/courses` - Управління курсами (CRUD)
- `/api/groups` - Управління групами (CRUD + зарахування учнів)
- `/api/students` - Управління учнями (читання + відвідуваність/платежі)
- `/api/attendance` - Відвідуваність та заняття
- `/api/payments` - Платежі та фінанси
- `/api/login/*` - Автентифікація (вже реалізовано)

**База даних (Supabase):**

Нові таблиці додані в `db_migrations/01_create_crm_tables.sql`:

1. `courses` - Курси
2. `groups` - Групи
3. `group_students` - Зарахування учнів до груп
4. `lessons` - Заняття
5. `attendance` - Відвідуваність
6. `payments` - Оплати

### Frontend (HTML/CSS/JavaScript)

**Структура:**

```
web/
├── css/
│   └── styles.css          # Єдиний файл стилів (CSS Variables)
├── js/
│   └── app.js              # Утиліти та API helper
├── admin/                  # Кабінет адміністратора
│   ├── dashboard.html
│   ├── courses.html
│   ├── groups.html
│   └── students.html
├── teacher/                # Кабінет вчителя
│   └── dashboard.html
├── parent/                 # Кабінет батьків
│   └── dashboard.html
├── student/                # Кабінет учня
│   └── dashboard.html
└── index.html              # Сторінка входу
```

## Дизайн система

### Кольорова палітра

```css
--primary: #6366F1;         /* Indigo */
--primary-light: #818CF8;
--primary-dark: #4F46E5;
--success: #10B981;         /* Emerald */
--warning: #F59E0B;         /* Amber */
--danger: #EF4444;          /* Red */
--info: #3B82F6;            /* Blue */
```

### Адаптивна верстка

- **Mobile** (< 768px): Bottom navigation
- **Tablet** (768px - 1024px): Збільшений контент
- **Desktop** (> 1024px): Sidebar navigation

## Функціональність за ролями

### Адміністратор (def/admin)
- ✅ Перегляд статистики (дашборд)
- ✅ Управління курсами (CRUD)
- ✅ Управління групами (CRUD)
- ✅ Перегляд списку учнів
- ⏳ Управління вчителями
- ⏳ Фінансові звіти

### Вчитель (teacher)
- ✅ Перегляд своїх груп
- ✅ Статистика по учням
- ⏳ Відмітка відвідуваності
- ⏳ Розклад занять
- ⏳ Домашні завдання

### Батьки (parent)
- ✅ Перегляд інформації про дітей
- ✅ Перегляд платежів
- ⏳ Розклад занять дитини
- ⏳ Прогрес та відвідуваність

### Учень (student)
- ✅ Перегляд своїх груп
- ⏳ Розклад занять
- ⏳ Домашні завдання
- ⏳ Досягнення

## Система автентифікації

### Множинні профілі

Система підтримує кілька профілів на один email:
- Один користувач може мати ролі: Вчитель + Батько
- При вході система показує вибір профілю
- Після вибору користувач перенаправляється до відповідного кабінету

### Безпека

- ✅ Паролі зберігаються за допомогою bcrypt
- ✅ Session-based аутентифікація через cookies
- ✅ Валідація даних на backend
- ✅ CORS налаштування

## API Документація

### Курси

**GET /api/courses**
```
Отримати список всіх курсів
Query params: is_active (boolean)
Response: { courses: [...] }
```

**POST /api/courses**
```
Створити новий курс
Body: { name, description, duration_months, age_min, age_max, price, is_active }
Response: { course: {...} }
```

**PUT /api/courses/:id**
```
Оновити курс
Body: { name?, description?, ... }
Response: { course: {...} }
```

**DELETE /api/courses/:id**
```
Деактивувати курс (м'яке видалення)
Response: { message: "..." }
```

### Групи

**GET /api/groups**
```
Отримати список груп
Query params: is_active, course_id, teacher_id
Response: { groups: [...] }
```

**GET /api/groups/:id**
```
Отримати групу з учнями
Response: { group: {..., students: [...]} }
```

**POST /api/groups**
```
Створити групу
Body: { name, course_id, teacher_id?, max_students, schedule?, room? }
Response: { group: {...} }
```

**POST /api/groups/:id/students**
```
Зарахувати учня до групи
Body: { student_id }
Response: { enrollment: {...} }
```

**DELETE /api/groups/:id/students/:student_id**
```
Відрахувати учня з групи
Response: { message: "..." }
```

### Відвідуваність

**GET /api/attendance/lessons**
```
Отримати заняття
Query params: group_id, date_from, date_to, status
Response: { lessons: [...] }
```

**POST /api/attendance/mark**
```
Відмітити відвідуваність
Body: { lesson_id, student_id, status, note? }
Status: present, absent, late, excused
Response: { attendance: {...} }
```

**POST /api/attendance/bulk-mark**
```
Масова відмітка відвідуваності
Body: { lesson_id, records: [{student_id, status, note?}] }
Response: { marked: 5, records: [...] }
```

### Платежі

**GET /api/payments**
```
Отримати платежі
Query params: student_id, parent_id, status, date_from, date_to
Response: { payments: [...] }
```

**POST /api/payments**
```
Створити платіж
Body: { student_id, parent_id?, amount, paid_at?, period_start?, period_end?, status? }
Response: { payment: {...} }
```

**GET /api/payments/stats**
```
Статистика платежів
Query params: date_from, date_to
Response: { total_amount, pending_amount, total_count, paid_count, pending_count }
```

## Установка та запуск

### 1. Встановлення залежностей

```bash
pip install -r requirements.txt
```

### 2. Налаштування змінних середовища

```bash
# Supabase
SUPABASE_URL1=your_main_db_url
HDD=your_main_db_key
SUPABASE_URL2=your_stock_db_url
HDD2=your_stock_db_key

# Auth
AUTH_TTL_HOURS=168  # 7 днів
COOKIE_SECURE=1

# Recovery
USE_TG_RECOVERY=1
USE_EMAIL_RECOVERY=1
```

### 3. Міграція бази даних

Виконайте SQL скрипт з `db_migrations/01_create_crm_tables.sql` у Supabase SQL Editor.

### 4. Запуск сервера

```bash
python main.py
```

Сервер запуститься на `http://localhost:8080`

## Тестування

### Ручне тестування

1. Відкрити `http://localhost:8080`
2. Зареєструватися або увійти
3. Перевірити доступ до різних кабінетів

### API тестування

```bash
# Тест отримання курсів
curl http://localhost:8080/api/courses

# Тест створення курсу (потрібна аутентифікація)
curl -X POST http://localhost:8080/api/courses \
  -H "Content-Type: application/json" \
  -d '{"name":"English A1","price":1500}'
```

## Наступні кроки (TODO)

### Високий пріоритет
- [ ] Додати управління вчителями в admin
- [ ] Розширити функціонал відвідуваності для вчителів
- [ ] Додати розклад занять (calendar integration)
- [ ] Реалізувати домашні завдання

### Середній пріоритет
- [ ] Звіти та аналітика
- [ ] Експорт даних (Excel/PDF)
- [ ] Email нотифікації
- [ ] Push notifications

### Низький пріоритет
- [ ] Dark mode
- [ ] Multilanguage support
- [ ] Mobile app (PWA)
- [ ] Інтеграція з платіжними системами

## Підтримка

Для питань та проблем створіть issue в GitHub репозиторії.

## Ліцензія

© 2024 EduVision CRM. Всі права захищені.
