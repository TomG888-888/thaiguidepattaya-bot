# USER_VK_TOKEN для VK Market

`USER_VK_TOKEN` нужен для автоматического создания товаров и загрузки фото в VK Market. Это пользовательский токен администратора группы, не токен сообщества.

## 1. Создать VK Standalone-приложение

1. Откройте раздел VK для разработчиков: `https://dev.vk.com/`.
2. Создайте приложение типа `Standalone` / `Standalone-приложение`.
3. Скопируйте `ID приложения` (`client_id`).

Если VK не даёт создать новое Standalone-приложение, используйте уже созданное приложение администратора.

## 2. Получить токен

Откройте в браузере ссылку, заменив `APP_ID` на ID приложения:

```text
https://oauth.vk.com/authorize?client_id=APP_ID&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=market,photos,groups,wall,offline&response_type=token&v=5.199
```

Подтвердите доступы. После редиректа на `oauth.vk.com/blank.html` токен будет в адресной строке после `access_token=`.

Нужные права:

- `market` — создание товаров VK Market
- `photos` — загрузка фото товаров
- `groups` — работа от имени/с группой
- `wall` — публикации на стену, если понадобится
- `offline` — токен без короткого срока жизни

## 3. Добавить токен в Railway

1. Откройте проект в Railway.
2. Перейдите в `Variables`.
3. Добавьте переменную:

```text
USER_VK_TOKEN=vk1.a....
```

4. Убедитесь, что также указаны:

```text
VK_GROUP_ID=...
VK_MARKET_CATEGORY_ID=1
```

5. Перезапустите deploy, если Railway не сделал это автоматически.

## 4. Проверить

В диалоге с ботом от имени `ADMIN_ID` выполните:

```text
/vk_market_test
```

Если проверка успешна, можно создавать товар:

```text
/create_product samet_2d_silver_sand
```
