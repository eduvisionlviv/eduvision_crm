# EduVision CRM (Appwrite)

Мінімальна, але модульна CRM для навчального закладу (2–18 років).
Побудована на Flask + Appwrite з готовими ендпоінтами для учнів,
батьків, курсів, оплат та збереження банківських ключів для
автоматичного зарахування платежів.

## Основні можливості
- **Ролі:** `admin`, `lc_manager`, `lc`, `teacher`, `parent`, `student`.
- **Модулі:** учні (розрахунок віку за датою народження), батьки/опікуни,
  курси, записи на курс, оплати за рік/місяць/заняття.
- **Безпека:** використання сесії `edu_session` (видає `/api/login/join`),
  перевірка ролей у кожному ендпоінті CRM, маскування секретів банку при
  читанні.
- **База:** Appwrite Databases з адаптером у `api/coreapiserver.py`.

## Нові таблиці в Appwrite
Назви можна змінювати, але за замовчуванням використовуються:
- `crm_students`
- `crm_parents`
- `crm_courses`
- `crm_enrollments`
- `crm_payments`
- `crm_bank_keys`

### Колекція користувачів (`contacts` → `user_admin`)
Щоб авторизація, скидання пароля та перевірки ролей працювали, у колекції `user_admin`
мають бути поля:

- `email` (`string`) — логін/пошта користувача.
- `passwordHash` (`string`) — збережений пароль або hash.
- `username` (`string`) — відображуване ім’я.
- `role` (`string`) — роль у CRM.
- `useradminId` (`string` або `int`) — внутрішній ID.
- `user_phone` (`string`) — номер телефону (для Telegram-прив’язки).
- `auth_tokens` (`string`) — останній виданий токен сесії.
- `expires_at` (`datetime`) — термін дії токена `edu_session`.
- `recovery_tg_id` (`string`) — ID Telegram для відновлення.
- `recovery_code` (`string`) — одноразовий код для скидання пароля.
- `password_resets_time` (`datetime`) — час видачі коду.

Усі текстові поля можна залишати як `string`, а час бажано зберігати у форматі
`datetime` Appwrite (ISO 8601, UTC). Без цих полів `/api/login/join` не зможе
видавати куку `edu_session` та перевіряти авторизацію.

## API: `/api/crm`
| Метод | Шлях | Призначення | Доступ |
|-------|------|-------------|--------|
| GET   | `/meta` | Метадані модулів та перелік ролей | усі авторизовані |
| GET   | `/students` | Список учнів з підрахованим віком | admin, lc_manager, lc, teacher |
| POST  | `/students` | Створити учня (`full_name`, `birth_date`, `parent_id`, `notes`) | admin, lc_manager, lc |
| GET   | `/students/<id>/age` | Вік учня в роках | admin, lc_manager, lc, teacher, parent |
| GET   | `/parents` | Список батьків/опікунів | admin, lc_manager, lc |
| POST  | `/parents` | Створити батька/опікуна | admin, lc_manager, lc |
| GET   | `/courses` | Список курсів | admin, lc_manager, lc, teacher |
| POST  | `/courses` | Створити курс (`name`, `age_from`, `age_to`, `description`) | admin, lc_manager, lc |
| GET   | `/enrollments` | Записи учнів на курси | admin, lc_manager, lc, teacher |
| POST  | `/enrollments` | Додати запис (`student_id`, `course_id`, `start_date`, `status`) | admin, lc_manager, lc |
| GET   | `/payments` | Перегляд оплат | admin, lc_manager, lc |
| POST  | `/payments` | Створити оплату (`payment_type`: `year`\|`month`\|`lesson`) | admin, lc_manager, lc |
| GET   | `/bank/keys` | Перегляд замаскованих банківських ключів | admin, lc_manager |
| POST  | `/bank/keys` | Зберегти ключі (`provider`, `api_key_id`, `api_secret`, `webhook_secret`) | admin, lc_manager |

## Налаштування
1. Додайте необхідні таблиці в Appwrite та прив’яжіть ID через змінні
   середовища `appwriteprojectid`, `appwritepadmin`, `appwritedatabaseid`,
   `APPWRITE_ENDPOINT`.
2. Запустіть сервер: `python main.py` (порт керується `PORT`, за
   замовчуванням 8080).
3. Для авторизації використовуйте логін `/api/login/join` — воно видасть
   куку `edu_session`, яку CRM читає автоматично.
