# pylint: disable=R0903,C0111,C0103,R0913

from sqlalchemy import Column, DateTime, Date, BigInteger, Text, DECIMAL, DDL, func, event
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow

db = SQLAlchemy()
ma = Marshmallow()


class Base(db.Model):
    __abstract__ = True

    id = Column(BigInteger, primary_key=True)
    created = Column(DateTime, nullable=False, server_default=func.now())
    updated = Column(DateTime)
    external_id = Column(Text, nullable=False, index=True, unique=True)


class PatientBase(Base):
    __abstract__ = True

    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)
    middle_name = Column(Text)
    date_of_birth = Column(Date, nullable=False)


class Patient(PatientBase):
    __tablename__ = 'patients'


# Это костылик для работы с партициями.
# Правильнее будет как-то так: https://github.com/sqlalchemy/sqlalchemy/wiki/PartitionTable
class PatientNew(PatientBase):
    __tablename__ = 'patients_new'

    def __init__(self, external_id, first_name, last_name, date_of_birth, middle_name=None):
        self.external_id = external_id
        self.first_name = first_name
        self.last_name = last_name
        self.date_of_birth = date_of_birth
        self.middle_name = middle_name


class PaymentBase(Base):
    __abstract__ = True

    amount = Column(DECIMAL(precision=10, scale=2), nullable=False)
    patient_id = Column(Text, nullable=False, index=True)


class Payment(PaymentBase):
    __tablename__ = 'payments'


class PaymentNew(PaymentBase):
    __tablename__ = 'payments_new'

    def __init__(self, external_id, patient_id, amount):
        self.external_id = external_id
        self.patient_id = patient_id
        self.amount = amount


class PatientStats(db.Model):
    __tablename__ = 'patients_stats'

    patient_id = Column(Text, primary_key=True)
    total_amount = Column(DECIMAL(precision=10, scale=2), nullable=False, index=True)


class PatientSchema(ma.ModelSchema):
    class Meta:
        model = Patient


class PaymentSchema(ma.ModelSchema):
    class Meta:
        model = Payment


patient_schema = PatientSchema()
patients_schema = PatientSchema(many=True)

payment_schema = PaymentSchema()
payments_schema = PaymentSchema(many=True)

event.listen(
    Patient.__table__,
    "after_create",
    DDL("""
        CREATE OR REPLACE FUNCTION patients_insert_trigger_func()
          RETURNS trigger
          LANGUAGE plpgsql
        AS
        $BODY$
        DECLARE
          old__id  BIGINT;
          old__crt TIMESTAMP;
          old__upd TIMESTAMP;
          old__fnm TEXT;
          old__lnm TEXT;
          old__dob DATE;
        BEGIN
          -- Ищем пациента в текущей базе
          SELECT id,
                 created,
                 updated,
                 first_name,
                 last_name,
                 date_of_birth
                 INTO old__id, old__crt, old__upd, old__fnm, old__lnm, old__dob
          FROM patients
          WHERE external_id = NEW.external_id
          LIMIT 1;
        
          -- Если нашли - используем старые id и created
          IF FOUND THEN
            NEW.id := old__id;
            NEW.created := old__crt;
            NEW.updated := old__upd;
            -- Если что-то изменилось - обновляем updated
            IF NEW.first_name <> old__fnm OR NEW.last_name <> old__lnm OR NEW.date_of_birth <> old__dob THEN
              NEW.updated := NOW();
            END IF;
          END IF;
        
          -- Ищем пациента в новой базе, т.е. проверяем на дубли. 
          old__id := NULL;
          EXECUTE format('SELECT 1 FROM %%I.%%I WHERE external_id = $1 LIMIT 1', TG_TABLE_SCHEMA, TG_TABLE_NAME)
          INTO old__id USING NEW.external_id;
        
          -- С EXECUTE не работает FOUND, пришлось такой костылик сделать
          IF old__id IS NOT NULL THEN
            -- Для простоты реализуем поведение ON CONFLICT ... DO NOTHING 
            RETURN NULL;
          END IF;
        
          RETURN NEW;
        END;
        $BODY$
    """)
)

event.listen(
    Payment.__table__,
    "after_create",
    DDL("""
        CREATE OR REPLACE FUNCTION payments_insert_trigger_func()
          RETURNS trigger AS
        $BODY$
        DECLARE
          old__id   BIGINT;
          old__crt  TIMESTAMP;
          old__upd  TIMESTAMP;
          old__amn  DECIMAL(10,2);
        BEGIN
          -- Ищем запись в текущей базе
          SELECT id,
                 created,
                 updated,
                 amount
                 INTO old__id, old__crt, old__upd, old__amn
          FROM payments
          WHERE external_id = NEW.external_id
          LIMIT 1;
        
          -- Если нашли - сохраняем id и created
          IF FOUND THEN
            NEW.id := old__id;
            NEW.created := old__crt;
            NEW.updated := old__upd;
            -- Если что-то изменилось - обновляем updated
            IF NEW.amount <> old__amn THEN
              NEW.updated := NOW();
            END IF;
          END IF;
        
          -- Реализуем поведение Foreign Key
          SELECT id INTO old__id FROM patients WHERE external_id = NEW.patient_id LIMIT 1;
          IF NOT FOUND THEN
            RETURN NULL; 
          END IF;
        
          old__id := NULL;
          EXECUTE format('SELECT 1 FROM %%I.%%I WHERE external_id = $1 LIMIT 1', TG_TABLE_SCHEMA, TG_TABLE_NAME)
          INTO old__id USING NEW.external_id;
        
          -- С EXECUTE не работает FOUND, пришлось такой костылик сделать    
          IF old__id IS NOT NULL THEN
            -- Для простоты реализуем поведение ON CONFLICT ... DO NOTHING
            RETURN NULL;
          END IF;
        
          RETURN NEW;
        END;
        $BODY$ LANGUAGE plpgsql;
    """)
)

event.listen(
    PatientNew.__table__,
    "after_create",
    DDL("DROP TABLE IF EXISTS %s" % PatientNew.__tablename__)
)

event.listen(
    PaymentNew.__table__,
    "after_create",
    DDL("DROP TABLE IF EXISTS %s" % PaymentNew.__tablename__)
)


def create_table(connection, table, has_trigger=True):
    """ Create a new table """
    connection.execute("DROP TABLE IF EXISTS {0}_new".format(table))
    connection.execute("CREATE TABLE {0}_new (LIKE {0} INCLUDING ALL)".format(table))
    if has_trigger:
        connection.execute("CREATE TRIGGER %s_before_insert_trigger " % table +
                           "BEFORE INSERT ON %s_new " % table +
                           "FOR EACH ROW EXECUTE PROCEDURE %s_insert_trigger_func()" % table)


def swap_and_drop_table(connection, table):
    """ Swap a new and an old tables and then removes an old one """
    connection.execute("ANALYSE {0}_new".format(table))
    connection.execute("ALTER TABLE IF EXISTS {0}_sub NO INHERIT {0}".format(table))
    connection.execute("ALTER TABLE IF EXISTS {0}_sub RENAME TO {0}_old".format(table))
    connection.execute("ALTER TABLE IF EXISTS {0}_new RENAME TO {0}_sub".format(table))
    connection.execute("ALTER TABLE IF EXISTS {0}_sub INHERIT {0}".format(table))
    connection.execute("DROP TABLE IF EXISTS {0}_old".format(table))


def calculate_stats(connection):
    """ Calculate patients_stats """
    connection.execute("INSERT INTO patients_stats_new (patient_id, total_amount) " +
                       "SELECT patient_id, SUM(amount) FROM payments_new GROUP BY patient_id")
