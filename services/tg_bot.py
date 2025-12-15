===== Application Startup at 2025-12-15 17:59:37 =====

[2025-12-15 18:00:04 +0000] [1] [INFO] Starting gunicorn 23.0.0
[2025-12-15 18:00:04 +0000] [1] [INFO] Listening at: http://0.0.0.0:7860 (1)
[2025-12-15 18:00:04 +0000] [1] [INFO] Using worker: gthread
[2025-12-15 18:00:04 +0000] [6] [INFO] Booting worker with pid: 6
⏭️  Пропущено __init__.py: немає install.txt
2025-12-15 18:00:06,268 [INFO] main: ✅ Blueprint 'attendance' loaded from attendance.py
2025-12-15 18:00:06,275 [INFO] main: ✅ Blueprint 'courses' loaded from courses.py
2025-12-15 18:00:06,287 [INFO] main: ✅ Blueprint 'crm' loaded from crm.py
2025-12-15 18:00:06,295 [INFO] main: ✅ Blueprint 'groups' loaded from groups.py
2025-12-15 18:00:06,302 [INFO] main: ✅ Blueprint 'payments' loaded from payments.py
2025-12-15 18:00:06,306 [INFO] main: ✅ Blueprint 'students' loaded from students.py
2025-12-15 18:00:06,307 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2025-12-15 18:00:06,308 [INFO] main: ✅ Blueprint 'taskscheduler' loaded from taskscheduler.py
2025-12-15 18:00:06,311 [INFO] main: ✅ Blueprint 'universal' loaded from universal_api.py
2025-12-15 18:00:06,315 [INFO] main: ✅ Blueprint 'login_join' loaded from login/join.py
2025-12-15 18:00:06,316 [INFO] main: ✅ Blueprint 'login_auth' loaded from login/join.py
2025-12-15 18:00:06,317 [INFO] main: ✅ Blueprint 'login_tg' loaded from login/join.py
2025-12-15 18:00:06,325 [INFO] main: ✅ Blueprint 'reg_user' loaded from reg/users.py
2025-12-15 18:00:06,325 [INFO] coreapiserver: ✅ Global lock middleware activated (coreapiserver)
2025-12-15 18:00:06,325 [INFO] main: ⏸️  Планувальник завдань (Scheduler) тимчасово вимкнено.
2025-12-15 18:00:06,329 [INFO] services.tg_bot: 🚀 Запуск Telegram бота...
2025-12-15 18:00:06,329 [INFO] main: Telegram-бот запущено у фоні.
2025-12-15 18:00:06,334 [WARNING] services.tg_bot: ⚠️ DNS помилка для api.telegram.org: [Errno -5] No address associated with hostname
2025-12-15 18:00:06,334 [INFO] services.tg_bot: 🚑 Використовую запасну IP: 149.154.167.220
2025-12-15 18:00:07,224 [INFO] httpx: HTTP Request: GET https://ezexbjchauhyamwktbnc.supabase.co/rest/v1/contacts?select=user_id%2Cpass_email&user_email=eq.gammmerx%40gmail.com&limit=1 "HTTP/2 200 OK"
2025-12-15 18:00:07,226 [INFO] bootstrap_user: Bootstrap user skipped: already hashed (user_id=1)
2025-12-15 18:00:26,521 [WARNING] services.tg_bot: Telegram API attempt 1/3 failed: timed out
2025-12-15 18:00:48,142 [WARNING] services.tg_bot: Telegram API attempt 2/3 failed: timed out
2025-12-15 18:01:11,241 [WARNING] services.tg_bot: Telegram API attempt 3/3 failed: timed out
2025-12-15 18:01:15,746 [ERROR] services.tg_bot: ❌ Telegram check failed completely. Skipping check. Error: timed out
2025-12-15 18:01:15,853 [ERROR] telegram.ext: Network Retry Loop (Bootstrap Initialize Application): Failed run number 0 of 0. Aborting.
Traceback (most recent call last):
  File "/usr/local/lib/python3.10/site-packages/httpx/_transports/default.py", line 101, in map_httpcore_exceptions
    yield
  File "/usr/local/lib/python3.10/site-packages/httpx/_transports/default.py", line 394, in handle_async_request
    resp = await self._pool.handle_async_request(req)
  File "/usr/local/lib/python3.10/site-packages/httpcore/_async/connection_pool.py", line 256, in handle_async_request
    raise exc from None
  File "/usr/local/lib/python3.10/site-packages/httpcore/_async/connection_pool.py", line 236, in handle_async_request
    response = await connection.handle_async_request(
  File "/usr/local/lib/python3.10/site-packages/httpcore/_async/connection.py", line 101, in handle_async_request
    raise exc
  File "/usr/local/lib/python3.10/site-packages/httpcore/_async/connection.py", line 78, in handle_async_request
    stream = await self._connect(request)
  File "/usr/local/lib/python3.10/site-packages/httpcore/_async/connection.py", line 124, in _connect
    stream = await self._network_backend.connect_tcp(**kwargs)
  File "/usr/local/lib/python3.10/site-packages/httpcore/_backends/auto.py", line 31, in connect_tcp
    return await self._backend.connect_tcp(
  File "/usr/local/lib/python3.10/site-packages/httpcore/_backends/anyio.py", line 113, in connect_tcp
    with map_exceptions(exc_map):
  File "/usr/local/lib/python3.10/contextlib.py", line 153, in __exit__
    self.gen.throw(typ, value, traceback)
  File "/usr/local/lib/python3.10/site-packages/httpcore/_exceptions.py", line 14, in map_exceptions
    raise to_exc(exc) from exc
httpcore.ConnectError: [Errno -5] No address associated with hostname

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/usr/local/lib/python3.10/site-packages/telegram/request/_httpxrequest.py", line 279, in do_request
    res = await self._client.request(
  File "/usr/local/lib/python3.10/site-packages/httpx/_client.py", line 1540, in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
  File "/usr/local/lib/python3.10/site-packages/httpx/_client.py", line 1629, in send
    response = await self._send_handling_auth(
  File "/usr/local/lib/python3.10/site-packages/httpx/_client.py", line 1657, in _send_handling_auth
    response = await self._send_handling_redirects(
  File "/usr/local/lib/python3.10/site-packages/httpx/_client.py", line 1694, in _send_handling_redirects
    response = await self._send_single_request(request)
  File "/usr/local/lib/python3.10/site-packages/httpx/_client.py", line 1730, in _send_single_request
    response = await transport.handle_async_request(request)
  File "/usr/local/lib/python3.10/site-packages/httpx/_transports/default.py", line 393, in handle_async_request
    with map_httpcore_exceptions():
  File "/usr/local/lib/python3.10/contextlib.py", line 153, in __exit__
    self.gen.throw(typ, value, traceback)
  File "/usr/local/lib/python3.10/site-packages/httpx/_transports/default.py", line 118, in map_httpcore_exceptions
    raise mapped_exc(message) from exc
httpx.ConnectError: [Errno -5] No address associated with hostname

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/usr/local/lib/python3.10/site-packages/telegram/ext/_utils/networkloop.py", line 134, in network_retry_loop
    await do_action()
  File "/usr/local/lib/python3.10/site-packages/telegram/ext/_utils/networkloop.py", line 109, in do_action
    await action_cb()
  File "/usr/local/lib/python3.10/site-packages/telegram/ext/_application.py", line 489, in initialize
    await self.bot.initialize()
  File "/usr/local/lib/python3.10/site-packages/telegram/ext/_extbot.py", line 318, in initialize
    await super().initialize()
  File "/usr/local/lib/python3.10/site-packages/telegram/_bot.py", line 854, in initialize
    await self.get_me()
  File "/usr/local/lib/python3.10/site-packages/telegram/ext/_extbot.py", line 1999, in get_me
    return await super().get_me(
  File "/usr/local/lib/python3.10/site-packages/telegram/_bot.py", line 985, in get_me
    result = await self._post(
  File "/usr/local/lib/python3.10/site-packages/telegram/_bot.py", line 703, in _post
    return await self._do_post(
  File "/usr/local/lib/python3.10/site-packages/telegram/ext/_extbot.py", line 372, in _do_post
    return await super()._do_post(
  File "/usr/local/lib/python3.10/site-packages/telegram/_bot.py", line 732, in _do_post
    result = await request.post(
  File "/usr/local/lib/python3.10/site-packages/telegram/request/_baserequest.py", line 198, in post
    result = await self._request_wrapper(
  File "/usr/local/lib/python3.10/site-packages/telegram/request/_baserequest.py", line 305, in _request_wrapper
    code, payload = await self.do_request(
  File "/usr/local/lib/python3.10/site-packages/telegram/request/_httpxrequest.py", line 303, in do_request
    raise NetworkError(f"httpx.{err.__class__.__name__}: {err}") from err
telegram.error.NetworkError: httpx.ConnectError: [Errno -5] No address associated with hostname
2025-12-15 18:01:15,867 [ERROR] services.tg_bot: ❌ Telegram bot crashed: httpx.ConnectError: [Errno -5] No address associated with hostname. Retrying in 10s...
2025-12-15 18:01:25,957 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
/app/services/tg_bot.py:231: RuntimeWarning: coroutine 'Application.shutdown' was never awaited
  time.sleep(10)
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
/app/services/tg_bot.py:231: RuntimeWarning: coroutine 'Application._bootstrap_initialize' was never awaited
  time.sleep(10)
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
2025-12-15 18:01:36,060 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:01:46,162 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:01:56,257 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:02:06,344 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:02:16,423 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:02:26,530 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:02:36,582 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:02:46,711 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:02:56,773 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:03:06,871 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:03:16,961 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
2025-12-15 18:03:27,027 [ERROR] services.tg_bot: ❌ Telegram bot crashed: Event loop is closed. Retrying in 10s...
 
