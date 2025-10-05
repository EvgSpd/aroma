#without matplotlib
import csv
import math
import numpy as np
import plotly.graph_objs as go
import plotly.offline as pyo
from datetime import datetime
from pandas import DataFrame

# Параметры модели (эмпирические)
ALPHA = 1e-3   # масштаб для k_evap
BETA = 1.0     # нормировочный для G
GAMMA_DEFAULT = 1.0  # коэффициент конкурентного подавления по рецептору (упрощение)

# Читаем CSV
def load_components(csv_path):
    data = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            comp = {
                'name': row['name'],
                'c': float(row['ci']),
                'Pvap': float(row['Pvap_Pa']),
                'M': float(row['M_g_mol']),
                'K': float(row['K']),
                'Ki_gel2air': float(row['Ki_gel2air']),
                'EFi': float(row['EFi']),
                'kai': {
                    'R_citrus': float(row['kai_R_citrus']),
                    'R_fruit' : float(row['kai_R_fruit']),
                    'R_spice' : float(row['kai_R_spice'])
                }
            }
            data.append(comp)
    return data

def k_evap(comp, alpha=ALPHA):
    return alpha * comp['Pvap'] / (math.sqrt(comp['M']) * comp['K'])

def G_in_air(comp, t, beta=BETA):
    k = k_evap(comp)
    return beta * comp['c'] * comp['Ki_gel2air'] * math.exp(-k * t)

def receptor_activation(data, t, receptors, gamma_map=None):
    if gamma_map is None:
        gamma_map = {}
    A = {}
    Gs = {comp['name']: G_in_air(comp, t) for comp in data}
    for r in receptors:
        numerator = sum(Gs[comp['name']] * comp['kai'].get(r, 0.0) for comp in data)
        denom = 1.0 + sum((gamma_map.get(comp['name'], GAMMA_DEFAULT) * Gs[comp['name']]) for comp in data)
        A[r] = numerator / denom
    return A

def sensory_contribution(data, t, receptors, gamma_map=None):
    contributions = {}
    Gs = {comp['name']: G_in_air(comp, t) for comp in data}
    for comp in data:
        RFi = sum(comp['kai'].values())
        contributions[comp['name']] = Gs[comp['name']] * comp['EFi'] * RFi
    A = receptor_activation(data, t, receptors, gamma_map)
    return contributions, A

def time_series(data, t_max=8*3600, n_points=800):
    receptors = ['R_citrus', 'R_fruit', 'R_spice']
    # лог-шаг: более плотный на ранних временах
    times_early = np.linspace(0, 1800, int(n_points*0.6))  # первые 30 мин
    times_late = np.linspace(1800, t_max, int(n_points*0.4))
    times = np.concatenate([times_early, times_late])
    series = {comp['name']: [] for comp in data}
    receptor_series = {r: [] for r in receptors}
    for t in times:
        contribs, A = sensory_contribution(data, t, receptors)
        for comp in data:
            series[comp['name']].append(contribs[comp['name']])
        for r in receptors:
            receptor_series[r].append(A[r])
    return times, series, receptor_series

def plot_plotly(times, series, receptor_series, out_html='perfume_interactive.html'):
    traces = []
    for name, vals in series.items():
        traces.append(go.Scatter(x=times/60.0, y=vals, mode='lines', name=name))
    layout = go.Layout(title='Component contributions over time', xaxis=dict(title='Time (minutes)'), yaxis=dict(title='Sensory contribution (arb. units)'))
    fig = go.Figure(data=traces, layout=layout)
    pyo.plot(fig, filename=out_html, auto_open=False)

    # receptors
    traces_r = []
    for r, vals in receptor_series.items():
        traces_r.append(go.Scatter(x=times/60.0, y=vals, mode='lines', name=r))
    layout_r = go.Layout(title='Receptor activations over time', xaxis=dict(title='Time (minutes)'), yaxis=dict(title='Receptor activation (arb. units)'))
    fig_r = go.Figure(data=traces_r, layout=layout_r)
    pyo.plot(fig_r, filename=out_html.replace('.html','_receptors.html'), auto_open=False)
    return out_html, out_html.replace('.html','_receptors.html')
    
def write_xls(series, indices, out_xls ):
    min_indices=list( map(lambda x: int(times[x]/60), indices)  )
    _list=[]
    _header = ["component"] + [f"{i}_min" for i in min_indices]
    for key in series:
        _row =[series[key][i] for i in  indices]                    # first column is the dictionary key
        _list.append([key] + _row)
    DataFrame(_list,columns=_header).to_excel(out_xls ,index=False) #, header=False
    return None 

if __name__ == '__main__':
    data = load_components('components.csv')
    times, series, receptor_series = time_series(data, t_max=8*3600, n_points=1200)
    html1, html2 = plot_plotly(times, series, receptor_series, out_html='perfume_interactive.html')    
    write_xls(series, indices = [1, 25, 120,700 ,820, ] , out_xls='info_pd.xls' )
    print(f"Saved interactive HTMLs: {html1}, {html2}")