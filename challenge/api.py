# pylint: disable=W0611,C0111,C0103

import math
import simplejson as json  # Нужн для корректной сериализации DECIMAL в JSON

from flask import Blueprint, jsonify, request
from .models import Patient, PatientNew, Payment, PaymentNew, PatientStats
from .models import db, patients_schema, payments_schema
from .models import create_table, swap_and_drop_table, calculate_stats

api = Blueprint('api', __name__)

PER_PAGE = 100


def headers(current_page, total_entries):
    """ HATEOAS HTTP headers """
    total_pages = math.ceil(total_entries / PER_PAGE)
    meta = {
        "base": request.base_url,
        "self": current_page,
        "prev": max(current_page - 1, 1),
        "next": min(current_page + 1, total_pages),
        "last": total_pages
    }

    hateoas = "<%(base)s?page=%(self)d>; rel=self, <%(base)s?page=1>; rel=first"
    if meta['prev'] != meta['self']:
        hateoas += ", <%(base)s?page=%(prev)d>; rel=prev"
    if meta['next'] != meta['self']:
        hateoas += ", <%(base)s?page=%(next)d>; rel=next"
    hateoas += ", <%(base)s?page=%(last)d>; rel=last"

    return {'X-Pagination-Per-Page': PER_PAGE,
            'X-Pagination-Current-Page': current_page,
            'X-Pagination-Total-Pages': total_pages,
            'X-Pagination-Total-Entries': total_entries,
            'Link': hateoas % meta}


def patients_get():
    payment_min = request.args.get('payment_min', type=float)
    payments_max = request.args.get('payments_max', type=float)
    current_page = request.args.get('page', default=1, type=int)

    query = Patient.query
    if payment_min is not None or payments_max is not None:
        query = query.join(PatientStats, PatientStats.patient_id == Patient.external_id)
    if payment_min is not None:
        query = query.filter(PatientStats.total_amount >= payment_min)
    if payments_max is not None:
        query = query.filter(PatientStats.total_amount <= payments_max)

    result = patients_schema.dump(query.paginate(page=current_page, per_page=PER_PAGE).items)
    return jsonify(result.data), 200, headers(current_page, query.count())


def patients_post():
    # Реальный запрос от пользователя сюда долетать не должен
    # Файлик должен быть залит в хранилище, например на S3 через AWS Api Gateway
    # или с использованием модуля nginx-upload-module, в этом случае этот ендпоинт должен
    # получить ссылку на загруженный файл и поставить задачу в очередь.
    #
    # Весь код ниже - мое первое знакомство с Flask и SQLAlchemy,
    # и в реальном сервисе использоваться не должен
    if request.is_json:
        create_table(db.session, table=Patient.__tablename__)

        objects = []
        for patient in request.get_json(silent=True):
            objects.append(PatientNew(external_id=patient['externalId'],
                                      first_name=patient['firstName'],
                                      last_name=patient['lastName'],
                                      date_of_birth=patient['dateOfBirth']))
            if len(objects) >= 1000:
                db.session.bulk_save_objects(objects)
                objects.clear()

        db.session.bulk_save_objects(objects)
        objects.clear()

        swap_and_drop_table(db.session, table=Patient.__tablename__)
        db.session.commit()
        return jsonify({'status': 'OK'}), 201
    return jsonify({'status': 'error'}), 422


def payments_get():
    external_id = request.args.get('external_id', type=str)
    patient_id = request.args.get('patient_id', type=str)
    current_page = request.args.get('page', default=1, type=int)

    query = Payment.query.order_by(Payment.id)
    if external_id is not None:
        query = query.filter(Payment.external_id == external_id)
    if patient_id is not None:
        query = query.filter(Payment.patient_id == patient_id)

    result = payments_schema.dump(query.paginate(page=current_page, per_page=PER_PAGE).items)
    return jsonify(result.data), 200, headers(current_page, query.count())


def payments_post():
    if request.is_json:
        create_table(db.session, table=Payment.__tablename__)
        create_table(db.session, table=PatientStats.__tablename__, has_trigger=False)

        objects = []
        for patient in request.get_json(silent=True):
            objects.append(PaymentNew(external_id=patient['externalId'],
                                      patient_id=patient['patientId'],
                                      amount=patient['amount']))
            if len(objects) >= 1000:
                db.session.bulk_save_objects(objects)
                objects.clear()

        db.session.bulk_save_objects(objects)
        objects.clear()

        calculate_stats(db.session)
        swap_and_drop_table(db.session, table=Payment.__tablename__)
        swap_and_drop_table(db.session, table=PatientStats.__tablename__)
        db.session.commit()
        return jsonify({'status': 'OK'}), 201
    return jsonify({'status': 'error'}), 422


@api.route('/patients', methods=['POST', 'GET'])
def patients():
    method = patients_post if request.method == 'POST' else patients_get
    return method()


@api.route('/payments', methods=['POST', 'GET'])
def payments():
    method = payments_post if request.method == 'POST' else payments_get
    return method()
