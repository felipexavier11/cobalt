import os,random,secrets
from datetime import date
from fasthtml.common import *
from fastlite import *
from monsterui.all import *

def set_scope_before(req, sess):
    req.scope.setdefault('auth', sess.get('auth'))

def user_auth_before(req, sess):
    auth = req.scope.get('auth')
    if auth: return
    sess['next'] = req.url.path
    return Redirect('/login')
    
def mk_nav(auth=None):
    authed = [A(href='/tests/new')(H4('Test')), A(href='/tests')(H4('Data')), A(href='/logout')(H4('Logout'))]
    anon = [A(href='/login')(H4('Login'))]
    return NavBar(
        *(authed if auth else anon),
        brand=A(href='/')(H2('COBALT')),
        cls='bg-primary text-primary-content py-4 px-16')

def mk_shell(c, req):
    auth = req.scope.get('auth', None)
    return mk_nav(auth), Main(id='main')(c)

before = [
    Beforeware(set_scope_before),
    Beforeware(user_auth_before, skip=[r'/favicon\.ico', '/login', '/logout', '/'])]
    
app,rt = fast_app(
    title='COBALT',
    before=before,
    session_cookie='session_cobalt',
    secret_key=secrets.token_hex(32),
    hdrs=Theme.blue.headers(katex=True, apex_charts=True),
    body_wrap=mk_shell)

@rt
def index(): return Container(render_md(Path('README.md').read_text()))

RESEARCHER_USER,RESEARCHER_PASS = os.getenv('RESEARCHER_USER'),os.getenv('RESEARCHER_PASS')

@rt('/login')
def get(sess):
    if sess.get('auth'): return Redirect('/')
    return Div(cls='flex justify-center pt-4')(
        Card(
            H3('Researcher Login'),
            P(id='errormsg', cls=TextT.error+TextT.bold),
            Form(hx_post='/login', hx_target='#errormsg')(
                LabelInput('Username', id='username', name='username', autocomplete='username'),
                LabelInput('Password', id='password', name='password', type='password', autocomplete='current-password'),
                Button(cls=ButtonT.primary)('Log in')),
            cls='w-96'))

@rt('/login')
def post(sess, username:str, password:str):
    if username==RESEARCHER_USER and password==RESEARCHER_PASS:
        sess['auth'] = True
        return Redirect(sess.pop('next', '/'))
    else: return 'Wrong username/password.'

@rt
def logout(sess):
    sess.clear()
    return Redirect('/')

db = database('data/cobalt.db')

class Test: id:int; initials:str; birthday:str; sex:str; test_date:str; threshold:float; completed:bool=False; srt_db:float=0.0; srt_done:bool=False
class Trial: id:int; test_id:int; trial_num:int; gap_ms:float; answer:str; correct:str
class SrtTrial: id:int; test_id:int; trial_num:int; level_db:float; word:str; correct:bool
tests_db = db.create(Test, pk='id')
trials_db = db.create(Trial, pk='id', foreign_keys=[('test_id', 'test', 'id')])
srt_trials_db = db.create(SrtTrial, pk='id', foreign_keys=[('test_id', 'test', 'id')])

def sort_th(col, sort, dir):
    new_dir = 'desc' if col==sort and dir=='asc' else 'asc'
    mark = (' ↑' if dir=='asc' else ' ↓') if col==sort else ''
    return Th(A(hx_get=f'/tests?sort={col}&dir={new_dir}', hx_target='#tests-table', hx_swap='outerHTML', hx_push_url='true')(col+mark))

def row_link(tid, v): return Td(A(href=f'/tests/{tid}', cls='block w-full')(v))

@rt('/tests')
def get(sort:str='id', dir:str='desc'):
    cols = tests_db.columns_dict.keys()
    if sort not in cols: sort = 'id'
    tsts = list(map(asdict, tests_db(order_by=f'{sort} {"desc" if dir=="desc" else "asc"}')))
    if not tsts: return Div(cls='flex justify-center pt-8')(
        Card(
            H3('No tests found'),
            P('Create ', A(href='/tests/new', cls=AT.primary)('a new test'), ' to get started.'),
            cls=TextT.center))
    return Table(id='tests-table')(
        Thead(Tr(*[sort_th(col, sort, dir) for col in cols])),
        Tbody(*[Tr(*[row_link(tst['id'], tst[col]) for col in cols]) for tst in tsts]))

STEP,START_GAP,N_REVERSALS = 0.8,100.0,6

def step_state(gap, streak, last_dir, ok):
    "Advance staircase one trial; returns new gap, streak, direction, and whether it reversed"
    new_dir = None
    if ok:
        streak += 1
        if streak>1: gap,streak,new_dir = gap*STEP,0,'down'
    else: gap,streak,new_dir = gap/STEP,0,'up'
    return gap,streak,(new_dir or last_dir),bool(new_dir and last_dir and new_dir!=last_dir)

def replay(trls):
    "Derive current staircase state from a test's trials"
    gap,streak,last_dir,revs = START_GAP,0,None,[]
    for t in trls:
        gap,streak,last_dir,rev = step_state(gap, streak, last_dir, t.answer==t.correct)
        if rev: revs.append(gap)
    return gap,streak,last_dir,revs

def get_trials(tid): return trials_db(where='test_id=?', where_args=[tid], order_by='trial_num')

@rt('/tests/new')
def get():
    return Div(cls='pt-4 flex justify-center')(
        Card(
            H3('New test'),
            Form(method='post', action='/tests')(
                LabelInput('Initials', id='initials', name='initials', required=True),
                LabelInput('Birthday', id='birthday', name='birthday', type='date', required=True),
                Fieldset(
                    Legend(cls=TextT.medium)('Sex'),
                    DivHStacked(
                        LabelRadio('Male', id='sex-m', name='sex', value='M'),
                        LabelRadio('Female', id='sex-f', name='sex', value='F'),
                        LabelRadio('Other', id='sex-o', name='sex', value='O'),
                        cls='gap-4 p-4')),
                Button(cls=ButtonT.primary)('Start test')),
            cls='w-96'))

@rt('/tests')
def post(initials:str, birthday:str, sex:str):
    t = tests_db.insert(Test(initials=initials, birthday=birthday, sex=sex, test_date=str(date.today()), threshold=0.0))
    return Redirect(f'/tests/{t.id}')

def plot(x, y, xlabel='', ylabel='', title='', precision=0, cls=None, id=None, name=None, **kwargs):
    chart = dict(type='line', zoom=dict(enabled=False), toolbar=dict(show=False), height=380) | kwargs
    opts = dict(
        chart=chart,
        series=[dict(data=y, **({'name':name} if name else {}))],
        xaxis=dict(title=dict(text=xlabel), categories=x),
        yaxis=dict(title=dict(text=ylabel), decimalsInFloat=precision))
    if title: opts['title'] = dict(text=title)
    return ApexChart(opts=opts, cls=cls, id=id)

def patient_cards(t, **attrs):
    return DivHStacked(
        Card(
            P(f'Initials: {t.initials}'),
            P(f'Birthday: {t.birthday}'),
            P(f'Sex: {t.sex}'),
            cls='w-full'),
        Card(P(f'Threshold: {t.threshold:.1f} ms' if t.completed else 'Threshold: pending'),
            P(f'Test date: {t.test_date}'),
            P(f'Status: {'Completed' if t.completed else 'In progress'}'),
            cls='w-full'),
        cls='items-stretch gap-4', id='patient-card', **attrs)

def gap_chart(trl): return plot([t.trial_num for t in trl], [t.gap_ms for t in trl], 'Trial number', 'Gap (ms)', precision=0, name='Gap (ms)', cls='w-full')

def done_card(t, n):
    return Card(
        H4('Test complete'),
        P(f'Trials: {n}'),
        P(cls=TextPresets.bold_lg)(f'Threshold: {t.threshold:.0f} ms'),
        A(href='/tests/new', cls=AT.primary)('New test'))

def test_panel(tid):
    t = tests_db[tid]
    trl = get_trials(tid)
    gap,_,_,revs = replay(trl)
    panel = done_card(t, len(trl)) if t.completed else trial_card(tid, len(trl)+1, gap, revs, random.choice(['left','right']), toj_gain(t.srt_db))
    return Div(id='test-panel', cls='flex flex-col gap-4')(panel, gap_chart(trl))

@rt('/tests/{tid}')
def get(tid:int):
    t = tests_db[tid]
    hdr = (Script(src='/js/playStimulus.js'), patient_cards(t))
    if not t.srt_done: return Container(*hdr, srt_panel(tid), cls='flex flex-col gap-4 p-8')
    if not srt_ok(t.srt_db): return Container(*hdr, headroom_card(tid, t), cls='flex flex-col gap-4 p-8')
    return Container(*hdr, test_panel(tid), cls='flex flex-col gap-4 p-8')

@rt('/tests/{tid}/trials')
def post(tid:int, answer:str, correct:str):
    t = tests_db[tid]
    if t.completed: return test_panel(tid)
    trl = get_trials(tid)
    gap,streak,last_dir,revs = replay(trl)
    ngap,_,_,rev = step_state(gap, streak, last_dir, answer==correct)
    trials_db.insert(Trial(test_id=tid, trial_num=len(trl)+1, gap_ms=gap, answer=answer, correct=correct))
    if rev: revs.append(ngap)
    if len(revs)>=N_REVERSALS:
        tests_db.update(dict(id=tid, threshold=sum(revs[-4:])/4, completed=True))
        return test_panel(tid), patient_cards(tests_db[tid], hx_swap_oob='true')
    return test_panel(tid)

def css_arrow(dir, w='[2rem]', h='[1rem]'):
    side = 'l' if dir=='r' else 'r'
    return Span(cls=f'border-y-{h} border-y-transparent border-{side}-{w} border-{side}-current')

def trial_card(tid, num, gap, revs, side, lvl):
    btn_attrs = dict(type='button', name='answer', hx_post=f'/tests/{tid}/trials', hx_target='#test-panel', hx_vals=f'{{"correct":"{side}"}}')
    return Card(
        H4(f'Trial {num} — gap {gap:.1f} ms — reversals {len(revs)}/{N_REVERSALS}'),
        P('Put on headphones. Click play, then choose the ear that heard the sound first.'),
        Button(type='button', autofocus=True, onclick=f'playTOJ("{side}", {gap}, {lvl})')('Play sound'),
        DivHStacked(
            Button(**btn_attrs, value='left', cls=ButtonT.destructive+' flex-auto py-8', hx_trigger="click, keyup[key=='ArrowLeft'] from:body")(css_arrow('l')),
            Button(**btn_attrs, value='right', cls=ButtonT.primary+' flex-auto py-8', hx_trigger="click, keyup[key=='ArrowRight'] from:body")(css_arrow('r')),
            cls='gap-4 pt-4 w-full'))

def srt_panel(tid):
    t = tests_db[tid]
    trl = get_srt_trials(tid)
    lvl,_,revs = srt_replay(trl)
    return Div(id='srt-panel', cls='flex flex-col gap-4')(
        srt_card(tid, len(trl)+1, lvl, next_word(trl), revs),
        srt_chart(trl))

def srt_chart(trl): return plot([t.trial_num for t in trl], [t.level_db for t in trl], 'Trial number', 'Level (dB)', precision=0, name='Level (dB)', cls='w-full')

def srt_card(tid, num, lvl, word, revs):
    return Card(
        H4(f'Calibration trial {num} — {lvl:.0f} dB — reversals {len(revs)}/{SRT_REVERSALS}'),
        P('Play the word, then mark whether the patient repeated it correctly.'),
        P(cls='text-3xl font-bold tracking-wide py-2')(word),
        Button(type='button', onclick=f'playSpondee("{word}", {lvl})', cls=ButtonT.secondary)('Play word'),
        Form(hx_post=f'/tests/{tid}/srt', hx_target='#srt-panel', hx_swap='outerHTML')(
            Input(type='hidden', name='word', value=word),
            Input(type='hidden', name='level_db', value=str(lvl)),
            DivHStacked(
                Button(name='correct', value='1', cls=ButtonT.primary)('Correct'),
                Button(name='correct', value='0', cls=ButtonT.secondary)('Incorrect'),
                cls='gap-4 pt-4')))

def headroom_card(tid, t):
    return Card(
        H4(cls=TextT.error+TextT.bold)('Insufficient headroom'),
        P(f'SRT came out at {t.srt_db:.1f} dB, so the TOJ level would be {toj_gain(t.srt_db):.1f} dB — above full scale.'),
        P('Set the tablet volume to maximum and recalibrate.'),
        Form(method='post', action=f'/tests/{tid}/recalibrate')(Button(cls=ButtonT.primary)('Recalibrate')))

@rt('/tests/{tid}/srt')
def post(tid:int, word:str, level_db:float, correct:int):
    t = tests_db[tid]
    if t.srt_done: return
    trl = get_srt_trials(tid)
    lvl,last_dir,revs = srt_replay(trl)
    nlvl,ndir,rev = srt_step(lvl, last_dir, len(revs), bool(correct))
    srt_trials_db.insert(SrtTrial(test_id=tid, trial_num=len(trl)+1, level_db=level_db, word=word, correct=bool(correct)))
    if rev: revs.append(nlvl)
    if len(revs)>=SRT_REVERSALS:
        tests_db.update(dict(id=tid, srt_db=sum(revs[-4:])/4, srt_done=True))
        t = tests_db[tid]
        panel = headroom_card(tid, t) if not srt_ok(t.srt_db) else test_panel(tid)
        return Div(id='srt-panel')(panel), patient_cards(t, hx_swap_oob='true')
    return srt_panel(tid)

@rt('/tests/{tid}/recalibrate')
def post(tid:int):
    srt_trials_db.delete_where('test_id=?', [tid])
    tests_db.update(dict(id=tid, srt_db=0.0, srt_done=False))
    return Redirect(f'/tests/{tid}')

SRT_START,SRT_BIG,SRT_SMALL,SRT_REVERSALS,SRT_HEADROOM = -30.0,5.0,2.0,6,50.0
SPONDEES = ('abelha boneca cadeira').split()

def srt_step(lvl, last_dir, nrev, ok):
    "Advance SRT staircase one trial; returns new level, direction, and whether it reversed"
    step = SRT_BIG if nrev<1 else SRT_SMALL
    new_dir = 'down' if ok else 'up'
    return (lvl-step if ok else lvl+step),new_dir,bool(last_dir and new_dir!=last_dir)

def srt_replay(trl):
    "Derive current SRT staircase state from a test's trials"
    lvl,last_dir,revs = SRT_START,None,[]
    for t in trl:
        lvl,last_dir,rev = srt_step(lvl, last_dir, len(revs), t.correct)
        if rev: revs.append(lvl)
    return lvl,last_dir,revs

def get_srt_trials(tid): return srt_trials_db(where='test_id=?', where_args=[tid], order_by='trial_num')
def next_word(trl): return random.choice([w for w in SPONDEES if w not in {t.word for t in trl}] or SPONDEES)
def toj_gain(srt_db): return srt_db + SRT_HEADROOM
def srt_ok(srt_db): return srt_db <= -SRT_HEADROOM

serve()
