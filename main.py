import base64,csv,io,os,random,secrets
from datetime import date
import matplotlib,matplotlib.pyplot as plt
from fasthtml.common import *
from fastlite import *
from monsterui.all import *

matplotlib.use('Agg')
login_redir = Redirect('/login')

def before(req, sess):
    if os.getenv('DEV'): sess['auth'] = True
    auth = req.scope['auth'] = sess.get('auth', None)
    if not auth: return login_redir

bware = Beforeware(before, skip=[r'/favicon\.ico', '/login', '/'])
app,rt = fast_app(before=bware, session_cookie='cobalt_sess', secret_key=secrets.token_hex(32), hdrs=Theme.blue.headers(katex=True))
@rt('/favicon.ico')
def favicon(): return FileResponse('favicon.ico')
@rt
def stimulus(): return FileResponse('stimulus.wav')
RESEARCHER_USER,RESEARCHER_PASS = os.getenv('RESEARCHER_USER'),os.getenv('RESEARCHER_PASS')
def mk_nav(auth=None):
    authed = [A('Test', href='/test'),
              A('Data', href=data),
              A('Logout', href='/logout')]
    anon   = [A('Login',  href='/login')]
    return NavBar(*(authed if auth else anon),
                  brand=A(H3('COBALT'), href=index),
                  id='navbar', cls='bg-primary text-primary-content py-4 px-16')
def mk_shell(sess, *content): return Title('COBALT'), mk_nav(sess.get('auth', None)), Main(*content, id='main')
@rt
def index(sess): return mk_shell(sess, Container(render_md(Path('README.md').read_text())))
@rt('/login')
def get(sess):
    if sess.get('auth'): return Redirect('/')
    return mk_shell(sess, Div(Card(
        H3('Researcher Login'),
        P(id='errormsg', cls='text-red-500'),
        Form(LabelInput('Username', id='username', name='username', autocomplete='username'),
             LabelInput('Password', id='password', name='password', type='password', autocomplete='current-password'),
             Button('Log in', cls=ButtonT.primary),
             hx_post='/login', hx_target='#errormsg'), cls='w-96'), cls='flex justify-center pt-4'))

@rt('/login')
def post(req, sess, username:str, password:str):
    if username==RESEARCHER_USER and password==RESEARCHER_PASS: sess['auth'] = True
    if not sess.get('auth'): return 'Wrong username or password.'
    return Redirect('/')

@rt
def logout(req, sess):
    sess.clear()
    return Redirect('/')
db = database('cobalt.db')
class Trial: id:int; initials:str; birthday:str; sex:str; test_date:str; trial:int; gap_ms:float; answer:str; correct:str
trials = db.create(Trial, pk='id', transform=True)
@rt('/test')
def get(req, sess):
    if not sess.get('patient'):
        return mk_shell(sess, Div(Card(
            H3('Patient Information'),
            Form(LabelInput('Initials', id='initials', name='initials'),
                LabelInput('Birthday', id='birthday', name='birthday', type='date'),
                Label('Sex'),
                Select(Option('Male', value='M'), Option('Female', value='F'), Option('Other', value='O'), name='sex'),
                Button('Start Test', cls=ButtonT.primary, cls2='mt-4'),
                hx_post='/test', hx_target='body'), cls='w-96'), cls='pt-4 flex items-center justify-center'))

    state = get_state(sess)
    return test_page(sess)

@rt('/test')
def post(req, sess, initials:str, birthday:str, sex:str):
    sess['patient'] = dict(initials=initials, birthday=birthday, sex=sex)
    sess['state'] = mk_state()
    return Redirect('/test')
@rt('/respond')
def post(req, sess, answer: str, correct: str):
    state = get_state(sess)
    patient = sess.get('patient', {})
    is_correct = answer == correct
    state['trial'] += 1
    state['results'].append(is_correct)
    trials.insert(Trial(initials=patient.get('initials'), birthday=patient.get('birthday'), sex=patient.get('sex'), test_date=str(date.today()), trial=state['trial'], gap_ms=state['gap_ms'], answer=answer, correct=correct))

    new_direction = None
    step = 0.8
    if is_correct:
        state['correct_streak'] += 1
        if state['correct_streak'] >= 2:
            new_direction = 'down'
            state['gap_ms'] = state['gap_ms'] * step
            state['correct_streak'] = 0
    else:
        state['correct_streak'] = 0
        new_direction = 'up'
        state['gap_ms'] = state['gap_ms'] / step

    if new_direction and state['last_direction'] and new_direction != state['last_direction']: state['reversals'].append(state['gap_ms'])
    if new_direction: state['last_direction'] = new_direction
    sess['state'] = state
    return Redirect('/test')
def patient_thresholds(sex=None, date_from=None, date_to=None):
    q = "SELECT initials,birthday,sex,test_date,gap_ms FROM trial t1 WHERE trial=(SELECT MAX(trial) FROM trial t2 WHERE t2.initials=t1.initials AND t2.test_date=t1.test_date)"
    conds,params = [],[]
    if sex: conds.append("sex=?"); params.append(sex)
    if date_from: conds.append("test_date>=?"); params.append(date_from)
    if date_to: conds.append("test_date<=?"); params.append(date_to)
    if conds: q = f"SELECT * FROM ({q}) WHERE " + " AND ".join(conds)
    return list(db.execute(q, params))

def mk_histogram(rows):
    vals = [r[4] for r in rows]
    if not vals: return None
    fig,ax = plt.subplots(figsize=(8,4))
    ax.hist(vals, bins=100, color='steelblue', edgecolor='white')
    ax.set(xlabel='Gap (ms)', ylabel='Count', title='TOJ Thresholds')
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()

def mk_slicers(sex='', date_from='', date_to=''):
    frm = Form(
        Select(Option('All sexes',value=''),Option('Male',value='M'),Option('Female',value='F'),Option('Other',value='O'), name='sex'),
        LabelInput('From', id='date_from', name='date_from', type='date', value=date_from),
        LabelInput('To', id='date_to', name='date_to', type='date', value=date_to),
        Button('Filter', cls=ButtonT.primary),
        hx_get=data_chart, hx_target='#chart', cls='flex gap-4 items-end mt-4')
    return Div(frm, A('Download', href=data_csv.to(), cls=ButtonT.primary), cls='flex gap-4 items-end mt-4')

@rt
def data_chart(req, session, sex:str='', date_from:str='', date_to:str=''):
    rows = patient_thresholds(sex or None, date_from or None, date_to or None)
    img = mk_histogram(rows)
    return Div(P(f'{len(rows)} patient sessions'), Img(src=f'data:image/png;base64,{img}') if img else P('No data', cls='text-center text-gray-400 py-8'), id='chart')

@rt
def data_csv(req, session):
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = [col.name for col in trials.columns]
    w.writerow(cols)
    w.writerows([[getattr(r, c) for c in cols] for r in trials()])
    return Response(buf.getvalue(), media_type='text/csv', headers={'Content-Disposition':'attachment; filename="cobalt_data.csv"'})

@rt
def data(req, session):
    rows = trials()
    return htmx(req, Container(
        H3('Trial Data'),
        mk_slicers(),
        Div(id='chart', hx_get=data_chart, hx_trigger='load')))
serve()
