#!/usr/bin/env python
# pylint: disable=W0611,C0111,C0103

import os
import csv
import random
import time
import ijson

from flask_script import Manager, Server
from flask_script.commands import ShowUrls, Clean
from challenge import create_app, db
from challenge.models import create_table, swap_and_drop_table, calculate_stats

# default to dev config because no one should use this in
# production anyway
env = os.environ.get('APPNAME_ENV', 'dev')
app = create_app('challenge.settings.%sConfig' % env.capitalize())

manager = Manager(app)
manager.add_command("server", Server())
manager.add_command("show-urls", ShowUrls())
manager.add_command("clean", Clean())


@manager.shell
def make_shell_context():
    """ Creates a python REPL with several default imports
        in the context of the app
    """

    return dict(app=app, db=db)


@manager.command
def createdb():
    """ Creates a database with all of the tables defined in
        your SQLAlchemy models
    """

    db.create_all()


@manager.command
@manager.option('-f', '--file', help='File patch', dest='file')
def import_patients(file='patients.json'):
    """ Import patients.json """

    t1 = time.time()
    csv_patch = file + '.csv'
    print("Конвертируем %s в %s" % (file, csv_patch))
    json_file = open(file, 'rb')
    with open(csv_patch, 'w+') as csv_file:
        csv_writer = csv.writer(csv_file)
        for patient in ijson.items(json_file, 'item'):
            csv_writer.writerow([patient['externalId'],
                                 patient['firstName'],
                                 patient['lastName'],
                                 patient['dateOfBirth']])
    json_file.close()
    print("Сконвертировано за %s секунд" % (time.time() - t1))
    t = time.time()
    print("Загружаем %s в базу" % csv_patch)
    csv_file = open(csv_patch, 'rb')
    con = db.engine.connect()
    trx = con.begin()
    create_table(con, 'patients')
    cur = con.connection.cursor()
    cur.copy_from(csv_file, 'patients_new', sep=',',
                  columns=('external_id', 'first_name', 'last_name', 'date_of_birth'))
    cur.close()  # ???
    print("Загружено за %s секунд" % (time.time() - t))
    swap_and_drop_table(con, 'patients')
    trx.commit()
    con.close()
    csv_file.close()
    os.remove(csv_patch)
    print("Общее время %s секунд" % (time.time() - t1))


@manager.command
@manager.option('-f', '--file', help='File patch', dest='file')
def import_payments(file='payments.json'):
    """ Import payments.json """

    t1 = time.time()
    csv_patch = file + '.csv'
    print("Конвертируем %s в %s" % (file, csv_patch))
    json_file = open(file, 'rb')
    with open(csv_patch, 'w+') as csv_file:
        csv_writer = csv.writer(csv_file)
        for payment in ijson.items(json_file, 'item'):
            csv_writer.writerow([payment['externalId'], payment['patientId'], payment['amount']])
    json_file.close()
    print("Сконвертировано за %s секунд" % (time.time() - t1))
    t = time.time()
    print("Загружаем %s в базу" % csv_patch)
    csv_file = open(csv_patch, 'rb')
    con = db.engine.connect()
    trx = con.begin()
    create_table(con, 'payments')
    create_table(con, 'patients_stats', has_trigger=False)
    cur = con.connection.cursor()
    cur.copy_from(csv_file, 'payments_new', sep=',', size=1048576,
                  columns=('external_id', 'patient_id', 'amount'))
    cur.close()  # ???
    print("Загружено за %s секунд" % (time.time() - t))
    calculate_stats(con)
    swap_and_drop_table(con, 'payments')
    swap_and_drop_table(con, 'patients_stats')
    trx.commit()
    con.close()
    csv_file.close()
    os.remove(csv_patch)
    print("Общее время %s секунд" % (time.time() - t1))


@manager.command
@manager.option('-f', '--file', help='File patch', dest='file')
def import_patients_slow(file='patients.json'):
    """ Import patients.json without convertation to CSV """

    t = time.time()
    print("Загружаем %s в базу" % file)
    json_file = open(file, 'rb')
    con = db.engine.connect()
    trx = con.begin()
    create_table(con, 'patients')
    con.execute("PREPARE p1 (text, text, text, date) AS " +
                "INSERT INTO patients_new (external_id, first_name, last_name, date_of_birth) " +
                "VALUES ($1, $2, $3, $4)")
    for patient in ijson.items(json_file, 'item'):
        con.execute("EXECUTE p1 (%s, %s, %s, %s)", (patient['externalId'],
                                                    patient['firstName'],
                                                    patient['lastName'],
                                                    patient['dateOfBirth']))
    swap_and_drop_table(con, 'patients')
    trx.commit()
    con.close()
    json_file.close()
    print("Загружено за %s секунд" % (time.time() - t))


@manager.command
@manager.option('-f', '--file', help='File patch', dest='file')
@manager.option('-c', '--count', help='Items count', dest='count')
def seed_payments(file='payments_seed.json', count='1000000'):
    """ Seed payments_seed.json """

    t = time.time()
    print("Записываем %s объектов в файл %s" % (count, file))
    c = int(count)
    f = open(file, 'w')
    f.write('[')
    for x in range(0, c):
        f.write('{')
        f.write('''
  "amount": {2}.{3},
  "patientId": "usr{0}",
  "externalId": "pay{1}"
'''.format(random.randrange(1, 1000000, 1),
           random.randrange(1, 1000000000, 1),
           random.randrange(1, 100, 1),
           random.randrange(0, 99, 1))
                )
        f.write('}')
        if x < c - 1:
            f.write(', ')
    f.write(']')
    f.close()
    print("Записано за %s секунд" % (time.time() - t))


@manager.command
@manager.option('-f', '--file', help='File patch', dest='file')
@manager.option('-c', '--count', help='Items count', dest='count')
def seed_patients(file='patients_seed.json', count='1000000'):
    """ Seed patients_seed.json """

    t = time.time()
    print("Записываем %s объектов в файл %s" % (count, file))
    c = int(count)
    f = open(file, 'w')
    f.write('[')
    for x in range(0, c):
        f.write('{')
        f.write('''
  "firstName": "Rick_{0}_{1}",
  "lastName": "Deckard_{0}",
  "dateOfBirth": "2000-01-01",
  "externalId": "usr{0}"
'''.format(x, random.choice('abc'))
                )
        f.write('}')
        if x < c - 1:
            f.write(', ')
    f.write(']')
    f.close()
    print("Записано за %s секунд" % (time.time() - t))


if __name__ == "__main__":
    manager.run()
