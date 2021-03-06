import logging
import os

from flask import Flask, request, redirect, url_for, jsonify
from flask_babel import Babel, gettext
from flask_sqlalchemy import SQLAlchemy

from util import session_util, file_util
from util.schedule_util import start_schedule

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
babel = Babel(app)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 6307200
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////etc/v2-ui/v2-ui.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
db = SQLAlchemy(app)
need_login_bps = []
common_context = {}

LANGUAGES = {
    'zh': '中文',
    'zh_CN': '中文',
    'en': 'English',
    'en_US': 'English',
    'es': 'Español',
}


@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(LANGUAGES.keys())


def init_db():
    from v2ray.models import Inbound
    from base.models import User, Setting
    User.__name__.lower()
    Inbound.__name__.lower()
    Setting.__name__.lower()
    file_util.mkdirs('/etc/v2-ui/')
    db.create_all()
    create_first_account(db)

def create_first_account(db):
    from v2ray.models import Inbound
    from random import randint
    from uuid import uuid4
    port = randint(10000, 60000)
    listen = "0.0.0.0"
    protocol = "vmess"
    uuid = str(uuid4())
    settings = '{"clients":[{"id":"'+ uuid + '","alterId":64}],"disableInsecureEncryption":false}'
    stream_settings = '{"network":"tcp","security":"none","tcpSettings":{"header":{"type":"none"}}}'
    sniffing = '{"enabled":true,"destOverride":["http","tls"]}'
    remark = ""
    inbound = Inbound(port, listen, protocol, settings, stream_settings, sniffing, remark)
    db.session.add(inbound)
    db.session.commit()
    replace_info(port, uuid)

def replace_info(port, uuid):
    fin = open("/opt/v2-ui-master/templates/v2ray/v2ray_info.html", "rt")
    data = fin.read()
    data = data.replace('REPLACE_THIS_PORT', str(port))
    data = data.replace('REPLACE_THIS_UUID', uuid)
    fin.close()
    fin = open("/opt/v2-ui-master/templates/v2ray/v2ray_info.html", "wt")
    fin.write(data)
    fin.close()

def init_app():
    from util import config
    app.secret_key = config.get_secret_key()


def init_common_context():
    from util import config
    global common_context
    common_context = {
        'cur_ver': config.get_current_version(),
        'base_path': '' if app.debug else config.get_base_path(),
    }


def init_bps():
    from util import config
    from base.router import base_bp
    from server.router import server_bp
    from v2ray.router import v2ray_bp
    from v2ray.router import public_bp
    bps = [
        base_bp,
        v2ray_bp,
        public_bp,
        server_bp,
    ]
    if not app.debug:
        base_path = config.get_base_path()
        for bp in bps:
            bp.url_prefix = base_path + (bp.url_prefix if bp.url_prefix else '')
    global need_login_bps
    need_login_bps += [v2ray_bp, server_bp]
    [app.register_blueprint(bp) for bp in bps]


def init_v2_jobs():
    from util import v2_jobs
    v2_jobs.init()


def is_ajax():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@app.before_request
def before():
    from base.models import Msg
    if not session_util.is_login():
        for bp in need_login_bps:
            if request.path.startswith(bp.url_prefix):
                if is_ajax():
                    return jsonify(Msg(False, gettext('You has been logout, please refresh this page and login again')))
                else:
                    return redirect(url_for('base.index'))


@app.errorhandler(500)
def error_handle(e):
    from base.models import Msg
    logging.warning(e.__str__())
    response = jsonify(Msg(False, e.msg))
    response.status_code = 200
    return response


init_db()
init_app()
init_common_context()
init_bps()
init_v2_jobs()
start_schedule()
