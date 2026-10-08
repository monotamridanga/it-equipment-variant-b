# Публикация на GitHub — действия владельца учётной записи

Создайте **пустой публичный** репозиторий `it-equipment-variant-b` на https://github.com/new (Public; без автоматической инициализации README). Затем из каталога проекта выполните:

```bash
git remote remove origin  # только если origin указывает на учебный локальный сервер
git remote add origin https://github.com/ВАШ_ЛОГИН/it-equipment-variant-b.git
git push -u origin main
git push origin --all
git remote -v
```

Для HTTPS-аутентификации используйте Git Credential Manager / browser sign-in или подходящий токен, а не пароль учётной записи. Настройте правила защиты ветви `main` и команды по `docs/access.md` в Settings. Проверьте доступ к странице без входа в аккаунт. Добавьте реальную ссылку `https://github.com/ВАШ_ЛОГИН/it-equipment-variant-b` в раздел 2.1 DOCX и приложите снимок веб-страницы.

**Внимание**: данный архив включает локальный Git и учебное локальное удалённое хранилище. В GitHub автоматически ничего не загружалось. После извлечения архива относительный путь к учебному origin может измениться — замените его как указано выше.
