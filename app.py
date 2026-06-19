"""
Banco Solar - Sistema de Gestão de Bancos Solares
Aplicação Flask com painel público, painel de cliente e painel administrativo.
"""

import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash

app = Flask(__name__)
app.secret_key = 'banco-solar-secret-key-2026'

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def load_csv(filename):
    """Carrega um arquivo CSV do diretório de dados."""
    filepath = os.path.join(DATA_DIR, filename)
    return pd.read_csv(filepath)


# ─────────────────────────── ROTAS PÚBLICAS ───────────────────────────

@app.route('/')
def index():
    """Página pública de transparência do banco solar."""
    usuarios = load_csv('usuarios.csv')
    usinas = load_csv('usinas.csv')
    geracao = load_csv('geracao_mensal.csv')

    clientes = usuarios[usuarios['tipo'] == 'cliente']

    transparencia = {
        'economia_kw': round(clientes['economia_kw'].sum(), 1),
        'creditos': round(clientes['creditos'].sum(), 1),
        'kw_recebidos': round(clientes['kw_recebidos'].sum(), 1),
        'investido': round(clientes['investido'].sum(), 2),
        'cashback_orquideas': round(clientes['cashback_orquideas'].sum(), 2),
        'geracao_total_kwh': round(geracao['geracao_kwh'].sum(), 1),
        'co2_evitado_total': round(geracao['co2_evitado_kg'].sum(), 1),
        'num_usinas': len(usinas),
        'num_clientes': len(clientes),
    }

    # Dados para gráficos
    geracao_por_mes = geracao.groupby('mes').agg({
        'geracao_kwh': 'sum',
        'co2_evitado_kg': 'sum'
    }).reset_index().to_dict('records')

    geracao_por_usina = geracao.groupby('usina_id').agg({
        'geracao_kwh': 'sum'
    }).reset_index()
    nomes_usinas = usinas[['id', 'nome']].rename(columns={'id': 'usina_id'})
    geracao_por_usina = geracao_por_usina.merge(nomes_usinas, on='usina_id')
    geracao_por_usina_dict = geracao_por_usina[['nome', 'geracao_kwh']].to_dict('records')

    return render_template('index.html',
                           transparencia=transparencia,
                           geracao_por_mes=geracao_por_mes,
                           geracao_por_usina=geracao_por_usina_dict)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '').strip()

        usuarios = load_csv('usuarios.csv')
        user = usuarios[(usuarios['email'] == email) & (usuarios['senha'] == senha)]

        if not user.empty:
            user_data = user.iloc[0]
            session['user_id'] = int(user_data['id'])
            session['user_nome'] = user_data['nome']
            session['user_tipo'] = user_data['tipo']

            if user_data['tipo'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('cliente_dashboard'))
        else:
            flash('E-mail ou senha incorretos. Tente novamente.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Encerrar sessão."""
    session.clear()
    return redirect(url_for('index'))


# ─────────────────────────── ROTAS DO CLIENTE ───────────────────────────

@app.route('/cliente')
def cliente_dashboard():
    """Painel do cliente."""
    if 'user_id' not in session or session.get('user_tipo') != 'cliente':
        return redirect(url_for('login'))

    usuarios = load_csv('usuarios.csv')
    residencias = load_csv('residencias.csv')

    user = usuarios[usuarios['id'] == session['user_id']].iloc[0]
    residencia = residencias[residencias['usuario_id'] == session['user_id']]

    user_data = {
        'nome': user['nome'],
        'economia_kw': user['economia_kw'],
        'creditos': user['creditos'],
        'kw_recebidos': user['kw_recebidos'],
        'investido': user['investido'],
        'cashback_orquideas': user['cashback_orquideas'],
        'data_cadastro': user['data_cadastro'],
    }

    residencia_data = None
    if not residencia.empty:
        r = residencia.iloc[0]
        residencia_data = {
            'endereco': r['endereco'],
            'em_dia_banco': r['em_dia_banco'],
            'em_dia_concessionaria': r['em_dia_concessionaria'],
            'cashback_em_dia': r['cashback_em_dia'],
            'consumo_mensal_kwh': r['consumo_mensal_kwh'],
            'economia_mensal_rs': r['economia_mensal_rs'],
        }

    # Dados simulados de histórico mensal para o cliente
    meses = ['Set/25', 'Out/25', 'Nov/25', 'Dez/25', 'Jan/26', 'Fev/26', 'Mar/26', 'Abr/26']
    import random
    random.seed(session['user_id'])
    historico = {
        'meses': meses,
        'economia': [round(user['economia_kw'] / 8 * (0.8 + random.random() * 0.4), 1) for _ in meses],
        'creditos': [round(user['creditos'] / 8 * (0.7 + random.random() * 0.6), 1) for _ in meses],
        'kw_recebidos': [round(user['kw_recebidos'] / 8 * (0.8 + random.random() * 0.4), 1) for _ in meses],
    }

    return render_template('cliente.html',
                           user=user_data,
                           residencia=residencia_data,
                           historico=historico)


# ─────────────────────────── ROTAS DO ADMIN ───────────────────────────

@app.route('/admin')
def admin_dashboard():
    """Painel administrativo."""
    if 'user_id' not in session or session.get('user_tipo') != 'admin':
        return redirect(url_for('login'))

    usinas = load_csv('usinas.csv')
    geracao = load_csv('geracao_mensal.csv')
    residencias = load_csv('residencias.csv')
    usuarios = load_csv('usuarios.csv')

    # Dados das usinas
    usinas_data = usinas.to_dict('records')

    # Dados unificados
    total_capacidade = usinas['capacidade_kw'].sum()
    total_geracao_mensal = usinas['geracao_mensal_kwh'].sum()
    total_co2 = geracao['co2_evitado_kg'].sum()
    media_eficiencia = round(usinas['eficiencia_percent'].mean(), 1)

    dados_unificados = {
        'total_capacidade': total_capacidade,
        'total_geracao_mensal': total_geracao_mensal,
        'total_co2': total_co2,
        'media_eficiencia': media_eficiencia,
        'num_usinas_ativas': len(usinas[usinas['status'] == 'ativa']),
        'num_usinas_manutencao': len(usinas[usinas['status'] == 'manutencao']),
    }

    # Economia em relação à concessionária (tarifa média R$ 0,75/kWh)
    tarifa_concessionaria = 0.75
    tarifa_solar = 0.30
    economia_concessionaria = {
        'tarifa_concessionaria': tarifa_concessionaria,
        'tarifa_solar': tarifa_solar,
        'economia_percentual': round((1 - tarifa_solar / tarifa_concessionaria) * 100, 1),
        'economia_mensal_rs': round(total_geracao_mensal * (tarifa_concessionaria - tarifa_solar), 2),
    }

    # Residências beneficiárias
    res_com_usuarios = residencias.merge(
        usuarios[['id', 'nome']].rename(columns={'id': 'usuario_id'}),
        on='usuario_id'
    )
    residencias_data = res_com_usuarios.to_dict('records')

    # Estatísticas das residências
    total_residencias = len(residencias)
    em_dia_banco = len(residencias[residencias['em_dia_banco'] == 'sim'])
    em_dia_conc = len(residencias[residencias['em_dia_concessionaria'] == 'sim'])
    cashback_ok = len(residencias[residencias['cashback_em_dia'] == 'sim'])

    stats_residencias = {
        'total': total_residencias,
        'em_dia_banco': em_dia_banco,
        'em_dia_banco_pct': round(em_dia_banco / total_residencias * 100, 1),
        'em_dia_concessionaria': em_dia_conc,
        'em_dia_concessionaria_pct': round(em_dia_conc / total_residencias * 100, 1),
        'cashback_em_dia': cashback_ok,
        'cashback_em_dia_pct': round(cashback_ok / total_residencias * 100, 1),
    }

    # Geração mensal por usina (para gráficos)
    geracao_por_mes = geracao.groupby('mes').agg({
        'geracao_kwh': 'sum',
        'co2_evitado_kg': 'sum',
        'receita_rs': 'sum'
    }).reset_index().to_dict('records')

    # Geração individual por usina e mês
    geracao_individual = {}
    for _, usina in usinas.iterrows():
        usina_geracao = geracao[geracao['usina_id'] == usina['id']].sort_values('mes')
        geracao_individual[usina['nome']] = {
            'meses': usina_geracao['mes'].tolist(),
            'geracao': usina_geracao['geracao_kwh'].tolist(),
            'co2': usina_geracao['co2_evitado_kg'].tolist(),
            'receita': usina_geracao['receita_rs'].tolist(),
        }

    return render_template('admin.html',
                           usinas=usinas_data,
                           dados_unificados=dados_unificados,
                           economia_concessionaria=economia_concessionaria,
                           residencias=residencias_data,
                           stats_residencias=stats_residencias,
                           geracao_por_mes=geracao_por_mes,
                           geracao_individual=geracao_individual)


# ─────────────────────────── API ENDPOINTS ───────────────────────────

@app.route('/api/transparencia')
def api_transparencia():
    """API pública para dados de transparência."""
    usuarios = load_csv('usuarios.csv')
    geracao = load_csv('geracao_mensal.csv')
    clientes = usuarios[usuarios['tipo'] == 'cliente']

    return jsonify({
        'economia_kw': round(clientes['economia_kw'].sum(), 1),
        'creditos': round(clientes['creditos'].sum(), 1),
        'kw_recebidos': round(clientes['kw_recebidos'].sum(), 1),
        'investido': round(clientes['investido'].sum(), 2),
        'cashback_orquideas': round(clientes['cashback_orquideas'].sum(), 2),
        'geracao_total_kwh': round(geracao['geracao_kwh'].sum(), 1),
        'co2_evitado_total': round(geracao['co2_evitado_kg'].sum(), 1),
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
