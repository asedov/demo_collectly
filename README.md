# Collectly quick python backend challenge 

# Challenge description

We are running the web application which stores and exposes Patients and their Payments. 
The application must stay in sync with external users's system data and provide
some additional analytics on top of the data.

## Models 

As a sample, basic SQLAlchemy models are provided in models.py file.
Feel free to extend and modify them, but do not delete existing fields.

**external_id** field must contain id of an object in external system, and is  
unique in the external source. It is the only field guaranteed not to change. 
All other fields in external source ***can change***, including payment amount!

#### Fameworks/ORMs

You can use flask/django or other framework of choice, just convert the models
by yourself.
You can modify the project structure as you like, the boilerplate code
is provided only as an example.


## Required functionality

1. Implement web service which exposes methods
    * GET /patients?payment_min=10&payments_max=20
      - Returns list of patients with total amount of payments in supplied range (in 
      this example between $10 and $20) 
      - filters are optional
    
    * GET /payments?external_id=
      - Returns the list of payments, probably filtered by patient's external_id
      - filters are optional
      
2. Implement data sync
    Just for the sake of simplicity we assume all the data comes in one piece, which 
    should be replicated in the database. If something is missing in the upload,
    it means object has been deleted in external system. 
 
    * Option 1. POST /patients and POST /payments methods
    * Option 2. Import json files from the command line
       
3. `created` and `updated` model fields should be set appropriately to their names:
 when the object was created and when it was updated last time. 


## Sample data

Sample data is provided in patients.json and payments.json files. 

 
## Evaluation criteria

* Code as you will code for a production use. You can omit some of the boring stuff 
 if you leave the comment that it should be there. 
 Make performance/reliability decisions as for production with 1000x more data/load. 
* Challenge completion time is important, build the working version as fast as you can
* To sum up 2 previous points: do not waste time on what is NOT in the task requirements,
e.g. devops. 

## How to submit
* Clone the repo or start a new one. Do not fork it!
* Upload in public or private repository on github. In case of private, please share the access.
* Keep your commit history.

----

# Решение

## Как запустить

- Настроить venv
- Запустить локальный PostgreSQL или просто `docker-compose -up -d`
- Развернуть базу `python manage.py createdb`
- Вгрузить тестовые данные `python manage.py import_patients` и `python manage.py import_payments`
- Запустить сервер `python manage.py server`
- Открыть http://127.0.0.1:5000/patients

## Комментарии

Импорт в базу реализован в трех разных вариантах:
- API использует bulk insert пачками по 1000 объектов;
- Команды `python manage.py import_patients` и `python manage.py import_payments` используют [COPY](https://www.postgresql.org/docs/11/sql-copy.html) с промежуточной конвертацией JSON в CSV;
- Команда `python manage.py import_patients_slow` использует [PREPARE](https://www.postgresql.org/docs/current/sql-prepare.html).

Во входных данных могут быть дубли, для простоты реализовано поведение `ON CONFLICT ... DO NOTHING`;

Для базового нагрузочного тестирования есть seed-генераторы: `python manage.py seed_patients -c 1000` и `python manage.py seed_payments -c 1000`, по умолчанию генерируют файлы `patients_seed.json` и `payments_seed.json` соответсвенно.
Загрузить сгенерированные файлы можно, соответсвенно, командами `python manage.py import_patients -f patients_seed.json` и `python manage.py import_payments -f payments_seed.json`

## Бенчмарк

### `import_patients` vs `import_patients_slow` 100K
```
python manage.py seed_patients -c 100000
    Записываем 100000 объектов в файл patients_seed.json
    Записано за 0.5124630928039551 секунд


python manage.py import_patients -f patients_seed.json
    Конвертируем patients_seed.json в patients_seed.json.csv
    Сконвертировано за 6.512366771697998 секунд
    Загружаем patients_seed.json.csv в базу
    Загружено за 9.974704265594482 секунд
    Общее время 16.598230600357056 секунд

    

python manage.py import_patients_slow -f patients_seed.json
    Загружаем patients_seed.json в базу
    Загружено за 55.237975120544434 секунд
```
### `import_patients` 1M
```
python manage.py seed_patients -c 1000000
    Записываем 1000000 объектов в файл patients_seed.json
    Записано за 3.346630811691284 секунд


python manage.py import_patients -f patients_seed.json
    Конвертируем patients_seed.json в patients_seed.json.csv
    Сконвертировано за 65.86938071250916 секунд
    Загружаем patients_seed.json.csv в базу
    Загружено за 87.23417615890503 секунд
    Общее время 153.4321689605713 секунд
```
### `import_payments` 100K vs 1M
```
python manage.py seed_payments -c 100000
    Записываем 100000 объектов в файл payments_seed.json
    Записано за 0.7930209636688232 секунд


python manage.py import_payments -f payments_seed.json
    Конвертируем payments_seed.json в payments_seed.json.csv
    Сконвертировано за 6.872813940048218 секунд
    Загружаем payments_seed.json.csv в базу
    Загружено за 13.034481048583984 секунд
    Общее время 20.66389513015747 секунд




python manage.py seed_payments -c 1000000
    Записываем 1000000 объектов в файл payments_seed.json
    Записано за 9.553805828094482 секунд


python manage.py import_payments -f payments_seed.json
    Конвертируем payments_seed.json в payments_seed.json.csv
    Сконвертировано за 60.178430795669556 секунд
    Загружаем payments_seed.json.csv в базу
    Загружено за 138.33630418777466 секунд
    Общее время 207.83345079421997 секунд
```

## P.S.

- `POST` запросы должны быть с `Content-Type: application/json` и JSON должен быть передан в теле запроса;
- `/payments` принимает параметры `?external_id=501` и `?patient_id=5`;
- `/patients` принимает `?payment_min=1` и `?payments_max=10`;
- Реализована постраничная навигация - параметр `?page=1`;
- Частично реализованы [HATEOAS](https://en.wikipedia.org/wiki/HATEOAS) заголовки
- Подсчет количества элементов в коллекции сделан через `.count()` для упрощения кода, возможно ценой производительности;
- Штатную пагинацию на базе LIMIT/OFFSET так же можно заменить на более эффективный вариант, что даст больной прирост производительности (Execution Time: 781.113 ms vs. Execution Time: 0.476 ms);
- Можно избавиться от промежуточной конвертации в CSV, но я пока еще не умею работать с Python'овскими [генераторами](https://wiki.python.org/moin/Generators);
- Вопрос с сортировкой результатов пока оставим открытым, здесь тоже большой простор для оптимизации.