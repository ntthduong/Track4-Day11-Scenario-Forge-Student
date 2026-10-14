"""Build the report from full-budget evidence; never choose a policy using TEST."""
import json
import math
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from avsim import core, space, viewer
from lab11 import metrics

E = ROOT / 'evidence'
def read(name):
    return json.loads((E / f'{name}.json').read_text(encoding='utf-8'))
def number(v):
    return f'{v:.6g}'
def percent(v):
    return f'{100*v:.3f}%'
def table(headers, rows):
    def cell(value):
        return str(value).replace('|', '\\|')
    return '\n'.join(['| ' + ' | '.join(cell(h) for h in headers) + ' |',
                      '| ' + ' | '.join(['---']*len(headers)) + ' |'] +
                     ['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows])
def dump(name, data):
    (E / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2),encoding='utf-8')

mc, replay, hunt, estimates, fix, mine, meta = [read(n) for n in
    ('mc','replay','hunt','estimate','fix','mine','meta')]
assert all(not read(n)['_run']['quick'] for n in ('mc','replay','hunt','estimate','fix','mine'))
student_id = meta['_run']['mssv']
nat, seeds = space.student_variant(student_id)
chosen = fix['chosen']['policy']
baseline, updated = fix['baseline_test'], fix['chosen_test']
cloud = read('cloud')
observations = {}

# Supplementary trajectory readings: select examples after the official policy selection.
rep = next((p for p in replay['replay_only'] if p['contact']=='rear'), replay['replay_only'][0])
log = core.rollout(rep['params'], ego='human')
rr = core.rollout(rep['params'], others='replay', log=log)
reactive = core.rollout(rep['params'])
ev = metrics.ego_events(rr,0)[0]
observations['replay'] = dict(scenario=rep['scenario'], event=ev,
    logged_ego_v=float(log.F[0,ev['f'],core.EGO,4]),
    replay_ego_v=float(rr.F[0,ev['f'],core.EGO,4]),
    reactive_ego_events=metrics.ego_events(reactive,0))

mode_rows = []
sample_runs = []
comparison = None
for mode in hunt:
    if mode.startswith('_'):
        continue
    cases = [c for c in cloud if c['out']=='crash' and c['mode']==mode]
    if not cases:
        continue
    # Same last-four selection as the supplied export step.
    case = cases[-4:][0]
    r = core.rollout(case['params'])
    event = metrics.ego_events(r,0)[0]
    other = event['b'] if event['a']=='ego' else event['a']
    pose = r.F[0,event['f'],r.ids.index(other)]
    observations[mode] = dict(event=event, other=other, other_x=float(pose[0]), other_v=float(pose[4]),
        ego_v=float(r.F[0,event['f'],core.EGO,4]), sees_ped=float(r.EGO[0,event['f'],2]), params=case['params'])
    c2lead=np.flatnonzero(r.EGO[0,:event['f']+1,3]==core.C2)
    pedvisible=np.flatnonzero((r.EGO[0,:event['f']+1,2]>0.5)&(r.F[0,:event['f']+1,core.P1,4]>0.1))
    observations[mode]['first_c2_leader_t']=float(c2lead[0]*core.DT) if len(c2lead) else None
    observations[mode]['first_visible_moving_ped_t']=float(pedvisible[0]*core.DT) if len(pedvisible) else None
    sample_runs.append(dict(id='SHOT-'+mode,label=mode,params=case['params'],policy=dict(core.POLICY)))
    mode_rows.append((mode,len(cases),event['t'],other))
    if comparison is None:
        for c in cases[-20:]:
            changed = core.rollout(c['params'],policy=chosen)
            if not metrics.ego_events(changed,0):
                comparison = dict(id='FIX-'+mode,label=mode,params=c['params'])
                rb = core.rollout(c['params'])
                observations['comparison'] = dict(mode=mode,params=c['params'],
                    baseline_event=metrics.ego_events(rb,0)[0],chosen_events=[])
                break
viewer.export(str(E/'report_viewer.json'),sample_runs,title=f'{student_id}: report screenshots')
if comparison:
    viewer.export(str(E/'comparison_viewer.json'),[comparison],policy=chosen,baseline_policy={},
                  title=f'{student_id}: chosen policy (solid) vs baseline (ghost)')
dump('observations',observations)

parts = [f'MSSV: {student_id}\n\n# Lab 11 · Scenario Forge — báo cáo hoàn chỉnh\n',
    f'Thị trấn **{meta["_run"]["town"]}** (`meta.json: _run.town`); seed MC `{seeds["mc"]}`, '
    f'search `{seeds["search"]}`, TEST công khai `{seeds["test"]}` (`meta.json: seeds`). '
    'Tất cả bước dùng ngân sách mặc định, `quick=false`, không salt. '
    'MSSV chứa chữ được truyền nguyên vẹn qua `LAB11_MSSV`; xem `SUBMISSION.md`. '
    'Các trường JSON ghi dưới đây nằm trong `evidence/`. Số được làm tròn khi trình bày; file JSON giữ đủ độ chính xác.\n',
    '## 1. Phát lại log có trung thực không?\n',
    f'`replay.json: n={replay["n"]}`, `dropped_human_crash_logs={replay["dropped_human_crash_logs"]}`, '
    f'`n_used={replay["n_used"]}`, `crash_in_both={replay["crash_in_both"]}`.\n',
    table(['Cách chạy','Thất bại','front','rear','side'],[
        [n,replay[n]['crashes'],*[replay[n]['contact'].get(t,0) for t in ('front','rear','side')]]
        for n in ('replay','reactive')])+'\n',
    'Nguồn: `replay.json: replay.crashes/contact`, `reactive.crashes/contact`. Xe bám đuôi trong log vẫn chạy theo '
    'quỹ đạo đã ghi với người lái; nó không biết planner phanh sớm hơn và không phanh đáp lại. Vì vậy va chạm rear '
    'khi replay có thể là artefact của cách đánh giá. Trong thế giới phản ứng, xe sau điều chỉnh theo khe và tốc độ thực. '
    'Không phải mọi side crash của replay đều là rear; chúng cũng có thể do xe cắt làn tiếp tục quỹ đạo đã ghi.\n',
    f'Ví dụ `replay.json: replay_only` scenario **{rep["scenario"]}**, tiếp xúc `{rep["contact"]}`: '
    f'`observations.json: replay.event` ghi {ev["a"]}–{ev["b"]} tại {ev["t"]:.2f} s; '
    f'tốc độ ego trong log người lái {observations["replay"]["logged_ego_v"]:.3f} m/s, '
    f'ego planner khi replay {observations["replay"]["replay_ego_v"]:.3f} m/s ở cùng khung. '
    f'Chạy reactive không có thất bại ego, TTC nhỏ nhất {rep["min_ttc_reactive"]:.4f} s '
    '(`replay_only.min_ttc_reactive`). Các số ở `observations.json` là lần đọc quỹ đạo bổ sung, không thay số pipeline.\n',
    '## 2. Kịch bản bất khả thi\n',
    table(['Luật loại','Căn cứ'],[
        ['π²·3.5/(2·cutDur²) > μg','Gia tốc ngang cực đại của chuyển làn cosine vượt lực bám'],
        ['cutBrake > μg','Phanh sau nhập làn vượt gia tốc khả dụng do ma sát'],
        ['pedV > 2.5 m/s','Giới hạn đi bộ của bài lab; không phải giới hạn sinh học cho chạy bộ'],
        ['cutV ≤ 0 hoặc > 22 m/s','Loại tốc độ xe cắt làn ngoài miền đã định nghĩa']])+'\n',
    table(['Cuộc săn','Bất khả thi','found (mọi kiểu gặp trong cuộc săn)'],[
        [m,h['infeasible'],json.dumps(h['found'],ensure_ascii=False)] for m,h in hunt.items() if not m.startswith('_')])+'\n',
    f'Nguồn: `hunt.json: <mode>.infeasible/found`. Cuộc săn sinh nhiều kịch bản bất khả thi nhất là '
    f'`{max((m for m in hunt if not m.startswith("_")),key=lambda m:hunt[m]["infeasible"])}`. '
    'Thời gian chuyển làn cực ngắn hay tốc độ/ma sát cực đoan làm điểm nguy hiểm lớn, nên nếu không lọc, CEM dễ bị hút '
    'vào các tình huống không thể tạo ra. Đếm chúng là thất bại sẽ phóng đại rủi ro của miền vật lý hợp lệ. '
    f'`mc.json: infeasible={mc["infeasible"]}`; bộ chạy không mô phỏng/đếm các mẫu đó là thất bại, '
    'nhưng mẫu số MC vẫn là số draw ban đầu theo quy ước pipeline.\n',
    '## 3. Monte Carlo cho biết gì?\n',
    f'`mc.json: crashes={mc["crashes"]}`, `n={mc["n"]}`, `p={number(mc["p"])}={percent(mc["p"])}`; '
    f'Wilson 95% [`lo={number(mc["lo"])}`; `hi={number(mc["hi"])}`]. '
    f'Với sai số tương đối ±20%, xấp xỉ chuẩn cho lập ngân sách cho n≈1.96²(1−p)/(0.2²p), '
    f'tức khoảng **{math.ceil(96.04*(1-mc["p"])/mc["p"]):,}** draw; quy tắc hiếm 96/p≈'
    f'**{math.ceil(96/mc["p"]):,}**, khoảng {96/mc["p"]/mc["n"]:.1f} lần ngân sách hiện tại. '
    'Đây là dự toán, không thay khoảng Wilson khi đếm ít sự kiện.\n',
    table(['Kiểu','k','Wilson 95%'],[[m,d['k'],f'[{number(d["lo"])}; {number(d["hi"])}]'] for m,d in mc['per_mode'].items()])+'\n',
    'Nguồn: `mc.json: per_mode.<mode>.k/lo/hi`. Các kiểu k=0 phải báo **chưa thấy, cận trên như bảng**, '
    'không kết luận xác suất bằng 0. Đối với IS hỗn hợp phòng thủ, dùng cận `3/(0.2n)`, không dùng `3/ESS`.\n',
    '## 4. Importance sampling, ESS và suy biến\n']
is_rows=[]
for s in estimates['seeds']:
    for m,d in s['per'].items():
        ptext=number(d['p']) if d['hits'] else f'chưa thấy; U95={number(d["upper_zero_hits"])}'
        is_rows.append([s['seed'],m,ptext,d['hits'],number(d['ess']),number(d['top_share']),number(d['se'])])
parts += [table(['Seed','Kiểu','p hoặc cận trên','hits','ESS','top_share','se'],is_rows)+'\n',
    'Nguồn: `estimate.json: seeds[i].per.<mode>.p/hits/ess/top_share/se/upper_zero_hits`. '
    'Ước lượng là mean(w·y), không chia cho tổng trọng số. q=0.8q_CEM+0.2p nên w≤5. '
    'ESS đo độ phân tán trọng số toàn bộ mẫu; top_share là phần ước lượng một mẫu chiếm. '
    'top_share>0.5 nghĩa là hơn nửa kết quả do một mẫu mang, làm CI chuẩn khó đáng tin. '
    'top_share nhỏ cũng không chứng minh q đã phủ mọi vùng thất bại.\n',
    table(['Seed','total','Khoảng xấp xỉ'],[[s['seed'],number(s['total']),f'[{number(s["lo"])}; {number(s["hi"])}]'] for s in estimates['seeds']])+'\n']
totals=[s['total'] for s in estimates['seeds']]
dominant=[f'seed {s["seed"]}, {m}: {number(d["top_share"])}'
          for s in estimates['seeds'] for m,d in s['per'].items() if d['top_share']>0.5]
parts += [f'Tổng qua seed thay đổi từ {number(min(totals))} đến {number(max(totals))}, '
    f'tỷ số max/min={max(totals)/min(totals):.3f}; trung vị={number(float(np.median(totals)))} '
    f'so với MC {number(mc["p"])}. Đây là so sánh bất định, không chọn seed đẹp nhất. '
    f'MC điểm cao hơn trung vị IS {mc["p"]/float(np.median(totals)):.3f} lần: các seed không cho một '
    'con số ổn định và không đồng thuận tốt với MC. Không giải thích sai lệch này bằng cách chọn seed thuận mắt. '
    'CEM có thể phủ tốt một nhánh hiếm nhưng bỏ sót nhánh phổ biến hơn; trọng số lý thuyết không chệch '
    'không đảm bảo một lần chạy hữu hạn đủ đại diện. '
    f'Các trường top_share>0.5: {"; ".join(dominant) or "không có"}. '
    'Khoảng của total do bộ chạy tổng hợp là xấp xỉ, không tự chứng nhận các kiểu zero-hit đã biến mất; '
    'cần đọc cận riêng từng kiểu.\n',
    'Để so ngân sách với độ chính xác IS, dùng n_MC≈p(1−p)/se² cho từng ước lượng có hits và se>0; '
    'các con số sau phụ thuộc chính p ước lượng, không phải chứng minh hiệu quả trên xác suất thật:\n',
    table(['Seed','Kiểu','n MC cùng SE (xấp xỉ)'],[[s['seed'],m,math.ceil(d['p']*(1-d['p'])/d['se']**2)]
        for s in estimates['seeds'] for m,d in s['per'].items() if d['hits'] and d['se']>0])+'\n',
    f'`estimate.json: budget={estimates["budget"]}` = 4×(8×300+3×600) draw, gồm săn và đo; '
    'MC có 3.000 draw. Chi phí mô phỏng thực còn phụ thuộc mẫu bất khả thi. '
    f'`other` lấy từ MC: k={estimates["other"]["k"]}, n={estimates["other"]["n"]}, '
    f'cận hi={number(estimates["other"]["hi"])} (`estimate.json: other`). '
    'Không săn other vì nó gom các cơ chế chưa định danh, chưa có một điểm nguy hiểm đặc thù; '
    'bỏ nó sẽ làm tổng thiếu một phần tập thất bại.\n',
    '## 5. Các kiểu thất bại và hình 3D\n',
    table(['Kiểu tìm được trong cloud','Số điểm thất bại','Ví dụ t (s)','Đối tượng'],mode_rows)+'\n',
    'Nguồn số điểm: `cloud.json`, lọc `out=crash` và `mode`; nguồn khung/đối tượng: '
    '`observations.json: <mode>.event`. `report_viewer.json` chứa đúng các ví dụ ảnh. '
    'Ảnh lấy ở khung ngay sau event (chênh 0.05 s) để marker hiện rõ; nhãn thời gian của viewer làm tròn một chữ số.\n']
for mode,count,t,other in mode_rows:
    o=observations[mode]
    description = ('Xe C2 đang vượt xe buýt đỗ, lấn vào làn ego; C2 ở trước x=112 m và chạy chậm dưới 6 m/s. '
                   'Ego nhận nó làm xe trước quá muộn nên tiếp xúc.' if mode=='bus_bypass' else
                   'P1 đi ra sau xe buýt; ego phanh nhưng thân xe dừng chắn vạch. P1 đứng lại thay vì đi xuyên thân xe. '
                   'Sự kiện block được tính là thất bại dù không phải tiếp xúc vật lý.' if mode=='crosswalk_block' else
                   f'Tiếp xúc ego với {other}; xem vị trí và tốc độ tại event trong observations.json.')
    parts += [f'**{mode}**: {description} Ví dụ t={t:.2f} s; đối tượng x={o["other_x"]:.3f} m, '
              f'v={o["other_v"]:.3f} m/s, ego v={o["ego_v"]:.3f} m/s; kind=`{o["event"]["kind"]}`.\n',
              f'![{mode} tại khung thất bại](evidence/shots/{mode}.png)\n']
    if mode=='bus_bypass':
        leadtext = (f't={o["first_c2_leader_t"]:.2f} s' if o['first_c2_leader_t'] is not None
                    else 'chưa được nhận làm leader trước event')
        parts += [f'Trong ví dụ này, C2 được nhận làm leader: {leadtext} '
                  '(`observations.json: bus_bypass.first_c2_leader_t`); C2 chậm lại trước bus và tìm khe '
                  'để vào làn ego. Chênh lệch giữa nhận leader và event thể hiện thời gian planner còn lại để phanh.\n']
    if mode=='crosswalk_block':
        visibility = (f'khung đầu tiên đồng thời P1 đang đi và planner thấy P1 là t={o["first_visible_moving_ped_t"]:.2f} s'
                      if o['first_visible_moving_ped_t'] is not None else
                      'trước event không có khung nào đồng thời P1 đang đi và planner thấy P1')
        parts += [f'Người đi bộ không ngó qua bus (`params.pedLook={o["params"]["pedLook"]}`); '
                  f'{visibility} '
                  '(`observations.json: crosswalk_block.first_visible_moving_ped_t`). '
                  'P1 đợi khe mà mình nhìn thấy, ego có chế độ thận trọng khi tầm nhìn bị che; '
                  'bus che tầm nhìn làm hai quyết định không có cùng thông tin.\n']
missing=[m for m in ('bus_bypass','cut_in','crosswalk_block','rear_ended') if not any(row[0]==m for row in mode_rows)]
parts += [f'Chưa tìm được trong các điểm săn lưu: {", ".join(missing) or "không có"}. '
    'Điều này chỉ nói về không gian, score, seed và ngân sách đã thử; không chứng minh không thể xảy ra. '
    'Cận zero-hit trong IS/MC mới là cách định lượng giới hạn. Một CEM chung dễ co về basin dễ tối ưu nhất '
    '(ví dụ lách xe buýt), mất các cơ chế khác như chặn vạch. Bảng found ở câu 2 cho thấy ngay cả một cuộc săn '
    'nhắm một kiểu vẫn có thể gặp kiểu khác; cần score và proposal riêng.\n',
    '## 6. Sửa planner: chọn trên TRAIN, báo cáo trên TEST\n',
    f'`fix.json: chosen.policy = {json.dumps(chosen)}`. Giữ nguyên danh sách ứng viên của repo, '
    'không thêm ứng viên theo kết quả TEST. choose_policy chọn fail_hi TRAIN nhỏ nhất trong các hàng '
    'có progress≥95% baseline, hòa thì lấy progress lớn hơn. TEST dùng seed mới và săn lại dưới từng policy.\n',
    table(['Tập / policy','fail','fail_hi_seen','fail_hi','progress (m)','harsh (frame/chuyến)','unseen'],[
        [name,number(row['fail']),number(row['fail_hi_seen']),number(row['fail_hi']),number(row['progress']),number(row['harsh']),', '.join(row['unseen']) or '—']
        for name,row in [('baseline TRAIN',fix['baseline_train']),('chosen TRAIN',fix['chosen']),('baseline TEST',baseline),('chosen TEST',updated)]])+'\n',
    'Nguồn: `fix.json: baseline_train/chosen/baseline_test/chosen_test` và các trường tương ứng. '
    'harsh đếm **khung** a<−3 m/s², không phải số pha phanh độc lập; quãng đường bị cắt tại thất bại đầu tiên.\n',
    f'Giảm quãng đường TRAIN {(1-fix["chosen"]["progress"]/fix["baseline_train"]["progress"])*100:.3f}%; '
    f'TEST {(1-updated["progress"]/baseline["progress"])*100:.3f}%. '
    'fail_hi_seen chỉ cộng kiểu có hits; fail_hi TEST còn cộng 3/(0.2×400)=0.0375 cho mỗi kiểu zero-hit và '
    'Wilson cho va chạm ngoài hai kiểu được săn. Do đó bản sửa không thấy bus_bypass trong mẫu vẫn có thể có fail_hi '
    'lớn hơn fail điểm của bản gốc. Không thể chứng nhận xác suất nhỏ chỉ bằng vài trăm mẫu.\n',
    table(['Ứng viên TRAIN','fail','fail_hi','progress'],[[json.dumps(r['policy']),number(r['fail']),number(r['fail_hi']),number(r['progress'])] for r in fix['table']])+'\n',
    'Nguồn: `fix.json: table`. Giảm cautionV có thể khiến xe sau phải phanh mạnh hơn; tăng cutinLat có thể làm '
    'ego nhường xe làn bên sớm và thay đổi khe xe C2 chấp nhận. Cơ chế này không đơn điệu: '
    'planner đổi hành vi thì các tác nhân reactive cũng đổi. Chỉ coi một núm phản tác dụng khi hàng TRAIN '
    'cho thấy kết quả, không suy diễn rằng mọi thay đổi nghe an toàn đều tệ hơn.\n']
worse=[r for r in fix['table'] if r['fail']>fix['baseline_train']['fail'] and any(
    (k=='cautionV' and v<core.POLICY[k]) or
    (k in ('cutinLat','T','pedBuffer') and v>core.POLICY[k]) for k,v in r['policy'].items())]
if worse:
    w=max(worse,key=lambda r:r['fail'])
    parts += [f'Ví dụ TRAIN có fail cao hơn baseline: `{json.dumps(w["policy"])}`, '
              f'fail={number(w["fail"])} so với {number(fix["baseline_train"]["fail"])}. '
              'Đây là bằng chứng trên TRAIN; không đủ quy hoàn toàn cho một cơ chế nếu chưa chạy thí nghiệm đối chứng.\n']
else:
    parts += ['Trong bảng TRAIN này, chưa có ứng viên chỉnh theo hướng thận trọng nói trên có fail điểm cao hơn '
              'baseline; không bịa một kết quả phản tác dụng để khớp câu hỏi. Tác động tới phản ứng xe khác vẫn '
              'là cơ chế cần kiểm tra, và loss progress có thể làm một ứng viên an toàn không đủ điều kiện.\n']
if (E/'caution_counterexample.json').exists():
    cx=read('caution_counterexample')
    rb,rc=cx['baseline'],cx['cautious']
    parts += [f'**Đối chứng cùng kịch bản TRAIN:** `caution_counterexample.json: draw_index={cx["draw_index"]}`, '
              f'seed={cx["seed"]}. Với cautionV=7.5, C2 bắt đầu lấn ngang lúc '
              f'{rb["first_c2_lateral_move_t"]:.2f} s, sau khi bus rời lúc {cx["params"]["busGo"]:.2f} s; '
              f'baseline không có event ego. Với cautionV=5, C2 lấn từ {rc["first_c2_lateral_move_t"]:.2f} s '
              f'và ego nhận C2 làm leader lúc {rc["first_c2_leader_t"]:.2f} s, rồi va chạm '
              f'{rc["events"][0]["t"]:.2f} s. Khi đó ego gốc đã ở x={rb["at_cautious_contact"]["ego"][0]:.3f} m, '
              f'ego thận trọng mới ở x={rc["at_cautious_contact"]["ego"][0]:.3f} m. '
              'Đi chậm thay đổi khe mà C2 chấp nhận, nên xe khác lấn vào sớm hơn; không phải chỉ giảm tốc ego '
              'trên một quỹ đạo C2 cố định. Đây là ca phản tác dụng có thật trong mô phỏng. '
              f'Đồng thời `fix.json: table[0].bus_bypass.top_share={number(fix["table"][0]["bus_bypass"]["top_share"])}` '
              'cho thấy ước lượng TRAIN của núm này bị một mẫu chi phối; không suy ra xác suất thật tăng chắc chắn '
              'chỉ từ fail điểm và CI chồng lấn.\n']
    if (E/'shots'/'caution-counterexample.png').exists():
        parts += ['![Phản ví dụ cautionV 5: xe đặc va chạm, bóng mờ policy gốc tránh được](evidence/shots/caution-counterexample.png)\n']
if comparison:
    c=observations['comparison']
    parts += [f'Ví dụ `observations.json: comparison`: baseline thất bại kiểu {c["mode"]} tại '
              f'{c["baseline_event"]["t"]:.2f} s, policy được chọn không có event ego. '
              'Nạp `comparison_viewer.json`: xe đặc là bản sửa, bóng mờ là bản gốc.\n',
              '![Bản sửa và bóng mờ policy gốc](evidence/shots/policy-comparison.png)\n']
parts += ['## 7. Từ mô phỏng ra đường thật\n',
    table(['Giả định quan trọng ở thị trấn B','Dữ liệu thay thế cụ thể','Hướng sai lệch dự kiến'],[
        ['cutGap lognormal, median 12 m','Quỹ đạo và kích thước xe từ video drone được hiệu chuẩn tại đoạn phố có xe buýt; inD là ví dụ dữ liệu quỹ đạo giao lộ để xây quy trình đo. Đo khe trước/sau tại thời điểm bắt đầu nhập làn, gồm cả lần từ chối khe.','Nếu người thật chấp nhận khe nhỏ hơn thì mô hình thường đánh giá thấp cut-in/bus_bypass; cần kiểm tra tương tác reactive để xác nhận.'],
        ['pedLook Bernoulli 0.85; pedGap lognormal median 4.5 s','Thu thập video tại bến xe buýt sát vạch, gán nhãn vị trí đầu/thân, bước ra nhìn, bus occlusion và thời gian xe đến. Có danh sách cả lượt chờ lẫn lượt qua; không lấy orientation đơn lẻ làm bằng chứng chắc chắn về gaze.','Nếu ít người nhìn qua xe buýt hơn hoặc chấp nhận khe ngắn hơn thì dự kiến crosswalk_block tăng.'],
        ['wet=0.30, μwet=0.5 và μdry=0.8','Tần suất mặt đường ướt từ log camera/mưa theo đúng tuyến và giờ; đo deceleration/ABS/IMU trên đường thử ở tốc độ tương ứng, kết hợp đo ma sát mặt đường theo FHWA.','Nếu μ thật thấp hơn hoặc tỷ lệ ướt cao hơn, khoảng dừng tăng và rủi ro thường bị đánh giá thấp; số skid chuẩn hóa không tự bằng μ của mọi lốp/tốc độ.']])+'\n',
    'Đây là kế hoạch hiệu chỉnh, chưa thu dữ liệu thật cho bài này. Nguồn dữ liệu/quy trình: '
    '[bài báo inD của tác giả](https://arxiv.org/abs/1911.07602), '
    '[FHWA locked-wheel tester](https://infotechnology.fhwa.dot.gov/locked-wheel-tester/). '
    'inD cung cấp quỹ đạo người tham gia giao thông từ drone; cần kiểm tra miền dữ liệu trước khi dùng cho phố có bus ở đây. '
    'Các hướng sai lệch là giả thuyết cơ chế, không phải hệ số đã đo.\n',
    '## 8. Giới hạn\n',
    '1. Chỉ một đoạn phố, 24 s và 16 tác nhân nền; không đo rủi ro cả mạng đường, đường cao tốc hoặc nhiều giờ chạy.\n'
    '2. Xe khác dùng IDM/gap acceptance quy tắc, người đi bộ theo thời gian-khe và vật cản; chưa có phân tâm, dự báo ý định đa dạng hay phân phối được fit từ người thật.\n'
    '3. Planner có state chính xác với che khuất hình học, chủ yếu do bus trong thế giới nền; không mô phỏng đầy đủ lỗi detection, tracking, trễ cảm biến hay lỗi định vị. Hazard oracle có kiểm tra đường nhìn đối với thân xe.\n\n'
    'Nếu thêm một tuần: thu dữ liệu hiệu chỉnh ba prior ở câu 7, chạy sensitivity trước khi tune, tăng ngân sách độc lập cho kiểu zero-hit '
    '(muốn cận 10⁻³ với beta=0.2 cần khoảng 15.000 draw/kiểu), thử trễ cảm biến và planner có dự đoán chuyển ngang của xe đạp. '
    'Không dùng TEST hiện tại để chọn lại policy rồi báo như holdout.\n',
    '## 9. Rắc rối riêng: xe đạp chuyển ngang từ làn ngoài\n',
    'Cảnh được dựng trong chương 10: H0 ở x=65 m, làn E2, d=0.7 m, v=5.5 m/s; '
    'khi ego còn cách 12 m thì lạng trái 3.4 m trong 2.7 s. Tình huống tương ứng một người đi xe đạp '
    'chuyển hẳn khỏi vùng cản mép đường. Không khẳng định ổ gà nhỏ khiến người lái lệch 3.4 m. '
    'Planner gốc chỉ nhận xe trong corridor ngang cutinLat=2.15 m, nên có thể phản ứng trễ với ý định chuyển vào làn.\n',
    f'`mine.json: exact.planner = {json.dumps(mine["exact"]["planner"])}`; '
    f'`accepted={number(mine["accepted"])}={percent(mine["accepted"])}; infeasible={mine["infeasible"]}`. '
    'Không có overlap khi mở cảnh; giới hạn và space được kiểm tra bằng studio.\n',
    table(['Trường space','Khoảng','Căn cứ'],[
        ['h0_x','45–85 m','±20 m quanh cảnh x=65; sweep thiết kế riêng thấy va chạm tránh được ở x=45,65,85 khi trig=12'],
        ['h0_v','4.8–6 m/s','17.28–21.6 km/h, nằm trong dải tốc độ thiết kế thông thường 16–24 km/h của NACTO'],
        ['h0_d / h0_swerve','0.5–0.9 m / 3.2–3.6 m','Tâm làn cách 3.5 m; tâm bike cuối z=2.15–2.95, vào corridor thân ego'],
        ['h0_swDur','2.6–3 s','a_lat tối đa π²·3.6/(2·2.6²)=2.628 m/s² <3 và <0.5g'],
        ['h0_trig','10–14 m','Lân cận điểm kích hoạt 12 m; biên kiểm thử engineering phản ứng muộn']])+'\n',
    'Nguồn đầy đủ: `hazard.json: why`, [NACTO design controls](https://nacto.org/publication/urban-bikeway-design-guide/designing-bikeways-for-all-ages-and-abilities/design-controls-for-bicycle-facilities/), '
    '[NHTSA bicycle safety](https://www.nhtsa.gov/road-safety/bicycle-safety). Các nguồn hỗ trợ tốc độ/để khoảng trống; '
    'không cung cấp tần suất lạng hay phân phối space. Uniform độc lập là thiết kế stress test công khai.\n',
    table(['Policy','n hợp lệ','crashes','avoidable','unavoidable','unattributed','low_speed','avoidable_foreknown','overlap_at_start','P lỗi | hazard, Wilson 95%'],[
        [name,r['n'],r['crashes'],r['avoidable'],r['unavoidable'],r['unattributed'],r['low_speed'],r['avoidable_foreknown'],r['overlap_at_start'],f'{number(r["p"])} [{number(r["lo"])}; {number(r["hi"])}]']
        for name,r in [(n,mine[n]) for n in ('baseline','chosen') if n in mine]])+'\n',
    'Nguồn: `mine.json: baseline/chosen` và các trường tương ứng. **avoidable**: cùng prefix planner, '
    'phanh tối đa ngay khi hazard đã bắt đầu và nhìn thấy thì tránh được mọi thất bại ego. '
    '**unavoidable**: phép thử phanh đó vẫn thất bại; không kết luận mọi phương án đánh lái đều bất lực. '
    '**unattributed**: thất bại không quy cho hazard, không chỉ đơn thuần là va chạm trước khi hazard bắt đầu. '
    'low_speed (<1 m/s) là cờ chồng lên các loại, không cộng lần thứ hai. '
    'avoidable_foreknown bỏ giới hạn nhìn thấy; chênh lệch với avoidable biểu thị cái giá che khuất.\n',
    'Chuẩn oracle lạc quan vì phản ứng tức thì, biết hazard ngay khi thấy và phanh tối đa: có thể đếm nhiều hơn '
    'số va chạm planner thực tế tránh được. Ngược lại chỉ thử phanh, không đánh lái, làm nó bỏ sót ca tránh được '
    'bằng hướng lái khác. Hai tác động ngược nhau nên không coi đây là ground truth lỗi planner tuyệt đối.\n',
    f'`hazard.json: exposure={mine["exposure"]}` **là giao thức thử**: cài một H0 mỗi chuyến, không phải tần suất '
    f'giao thông ngoài đời. `mine.json: baseline.per_trip={number(mine["baseline"].get("per_trip",float("nan")))}` '
    'chỉ áp dụng tuyến thử cố ý phơi nhiễm. Với exposure thực e chưa biết, f_bike(e)=e·P(avoidable | hazard). '
    'Không dùng exposure=1 để tuyên bố bike nguy hiểm hơn trong thị trấn thật.\n']
pb = mine['baseline']['p']
pbus=float(np.median([s['per']['bus_bypass']['p'] for s in estimates['seeds']]))
if pb>0:
    parts += [f'Trung vị IS bus_bypass={number(pbus)} (`estimate.json: seeds[].per.bus_bypass.p`); '
              f'hai tần suất bằng nhau khi e*=p_bus/p_bike={number(pbus/pb)}. '
              'Đây là ngưỡng sensitivity trên các prior giả định; muốn biết phía nào lớn hơn cần đo e ngoài đời.\n',
              f'Nếu thay p_bus bằng MC bus_bypass={number(mc["per_mode"]["bus_bypass"]["k"]/mc["n"])}, '
              f'ngưỡng tương ứng là e*={number((mc["per_mode"]["bus_bypass"]["k"]/mc["n"])/pb)}. '
              'Sự chênh lệch giữa hai ngưỡng phản ánh bất ổn IS ở câu 4; không chọn một ngưỡng làm sự thật.\n',
              table(['Exposure giả định cho sensitivity, không phải dữ liệu đo','f_bike / chuyến'],
                    [[e,number(e*pb)] for e in (0.001,0.01,0.1,1)])+'\n']
parts += ['![Xe đạp H0 tại tiếp xúc trong chương 10](evidence/shots/hazard-bike.png)\n',
    'Ảnh ở 13.9 s, ngay sau khung tiếp xúc 13.85 s của cảnh cố định (thanh viewer bước 0.05 s, nhãn làm tròn một chữ số). '
    'Chưa có thử lái do người dùng thực hiện; không báo kết quả người lái. '
    'Cách sửa: tăng cutinLat lên 3.0 đã được thử ở E và còn làm tình huống này tệ hơn, nên không coi tăng corridor '
    'là lời giải đã được chứng minh. Có thể sàng v0/T trên một TRAIN dành riêng cho hazard, với kiểm tra rear-end/progress, '
    'nhưng không chọn lại theo TEST vừa báo. Hướng sửa logic cụ thể là dự báo vận tốc ngang/ý định chuyển làn, '
    'tính giao cắt swept body với ego trong vài giây tới, phanh sớm và kiểm tra vị trí dừng nằm ngoài quỹ đạo bike; '
    'kiểm tra xe bám đuôi để tránh chỉ chuyển lỗi sang phía sau. Không sửa lõi avsim trong bài nộp.\n',
    '## Kiểm tra bổ sung và tái lập\n',
    '10 TODO đã triển khai theo docstring. 31 test công khai, 10 test parity và 3 test biên bổ sung '
    '(batch với xe đạp mới, thứ tự phân loại/biên 112 m và 6 m/s, CEM tie ổn định) được kiểm tra. '
    'Kết quả kiểm tra cuối nằm trong `evidence/validation.json`. Lõi, seed, phân phối và ứng viên gốc giữ nguyên. '
    'Rubric không có bonus riêng; kiểm tra biên, script tái lập và sensitivity exposure là phần mở rộng, không tự nhận điểm.\n']
if 'chosen' in mine:
    b,c=mine['baseline'],mine['chosen']
    conclusion = ('tăng' if c['p']>b['p'] else 'giảm')
    direction = 'lên' if c['p']>b['p'] else 'xuống'
    insertion = (f'Bản sửa ở E **không tổng quát hóa tốt sang hazard này**: P(avoidable | hazard) {conclusion} '
                 f'từ {percent(b["p"])} {direction} {percent(c["p"])} '
                 f'(`mine.json: baseline.p/chosen.p`); chênh lệch {100*(c["p"]-b["p"]):.3f} điểm phần trăm. '
                 f'Va chạm low_speed đổi từ {b["low_speed"]} sang {c["low_speed"]}. '
                 'Nhiều event ở tốc độ thấp là bike tiến vào thân xe đang chờ, không phải ego lao vào bike. '
                 'Phanh đến tốc độ thấp chưa đảm bảo thân xe dừng ở vị trí tránh được quỹ đạo ngang. '
                 'Một fix tốt trên hai kiểu được săn không tự chứng minh an toàn trên cơ chế mới. '
                 'Các Wilson trong bảng là khoảng biên riêng; không dùng công thức hai mẫu độc lập cho chênh lệch '
                 'vì hai policy chạy cùng các kịch bản.\n')
    parts.insert(parts.index('## Kiểm tra bổ sung và tái lập\n'),insertion)
(ROOT/'REPORT.md').write_text('\n'.join(parts),encoding='utf-8')
print('Built REPORT.md, supplementary trajectory readings and screenshot viewer files.',flush=True)
