import streamlit as st
import pandas as pd
import time
import json
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Tournament Master - Gestion 9 Equipes", layout="wide", page_icon="🏆")

# --- STYLE PERSONNALISÉ ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    .match-header { background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%); color: white; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .question-box { background-color: #fffbeb; border-left: 5px solid #f59e0b; padding: 15px; border-radius: 10px; margin: 10px 0; font-size: 1.2em; border: 1px solid #fef3c7; }
    .instruction-box { background-color: #eff6ff; border-left: 5px solid #3b82f6; padding: 15px; border-radius: 8px; font-style: italic; margin-bottom: 15px; color: #1e40af; }
    .format-info { background-color: #f0fdf4; border: 1px solid #16a34a; padding: 10px; border-radius: 5px; margin-bottom: 20px; }
    .sidebar-score { font-size: 1.1em; font-weight: bold; color: #1e3a8a; }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION ---
def init_session():
    if 'teams_df' not in st.session_state:
        st.session_state.teams_df = pd.DataFrame(columns=['Equipe', 'Joueur'])
    if 'questions_df' not in st.session_state:
        st.session_state.questions_df = pd.DataFrame(columns=['Manche', 'Rubrique', 'Question', 'Points', 'Temps', 'Consigne'])
    if 'matches' not in st.session_state:
        st.session_state.matches = {}
    if 'player_scores' not in st.session_state:
        st.session_state.player_scores = {}
    if 'match_progress' not in st.session_state:
        st.session_state.match_progress = {}

init_session()

# --- PERSISTENCE ---
def export_state_json():
    state = {
        "teams": st.session_state.teams_df.to_dict(orient='records'),
        "questions": st.session_state.questions_df.to_dict(orient='records'),
        "matches": st.session_state.matches,
        "player_scores": st.session_state.player_scores,
        "match_progress": st.session_state.match_progress
    }
    return json.dumps(state, indent=4)

def import_state_json(uploaded_json):
    try:
        data = json.load(uploaded_json)
        st.session_state.teams_df = pd.DataFrame(data["teams"])
        st.session_state.questions_df = pd.DataFrame(data["questions"])
        st.session_state.matches = data["matches"]
        st.session_state.player_scores = data["player_scores"]
        st.session_state.match_progress = data.get("match_progress", {})
        st.success("Configuration restaurée avec succès !")
        st.rerun()
    except Exception as e:
        st.error(f"Erreur de lecture du fichier JSON : {e}")

# --- LOGIQUE TOURNOI ---
def generate_schedule(teams):
    if len(teams) != 9:
        st.error(f"Le tournoi nécessite exactement 9 équipes (actuellement {len(teams)}).")
        return
    # Format triangulaire : 6 matchs, chaque équipe joue 2 fois
    indices = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8]]
    matches = {}
    for i, grp in enumerate(indices):
        mid = str(i+1)
        m_teams = [teams[j] for j in grp]
        matches[mid] = {'teams': m_teams, 'scores': {t: 0 for t in m_teams}, 'status': 'Prévu'}
        st.session_state.match_progress[mid] = {"q_idx": 0}
    st.session_state.matches = matches

# --- NAVIGATION ---
st.sidebar.title("🏆 Tournament Manager")
page = st.sidebar.radio("Navigation", ["Configuration & Sauvegarde", "Calendrier", "Console d'Arbitrage", "Classement Général"])

# --- PAGE 1 : SETUP ---
if page == "Configuration & Sauvegarde":
    st.title("📂 Paramètres du Tournoi")
    
    tab_import, tab_json = st.tabs(["📥 Importation CSV/Excel", "💾 Sauvegarde JSON"])
    
    with tab_import:
        st.markdown("""
        <div class='format-info'>
        <b>Structure imposée pour le fichier Questions :</b><br>
        Colonnes : <code>Manche</code>, <code>Rubrique</code>, <code>Question</code>, <code>Points</code>, <code>Temps</code>, <code>Consigne</code>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("👥 Equipes et Joueurs")
            f_teams = st.file_uploader("Fichier Equipes (9 équipes, 3 joueurs/équ)", type=['csv', 'xlsx'])
            if f_teams:
                df = pd.read_csv(f_teams) if f_teams.name.endswith('.csv') else pd.read_excel(f_teams)
                st.session_state.teams_df = df
                for p in df['Joueur'].unique():
                    if p not in st.session_state.player_scores: st.session_state.player_scores[p] = 0
                st.success(f"{len(df['Equipe'].unique())} équipes chargées.")
        
        with c2:
            st.subheader("❓ Banque de Questions")
            f_q = st.file_uploader("Fichier Questions (Format Imposé)", type=['csv', 'xlsx'])
            if f_q:
                df_q = pd.read_csv(f_q) if f_q.name.endswith('.csv') else pd.read_excel(f_q)
                required = ['Manche', 'Rubrique', 'Question', 'Points', 'Temps']
                if all(col in df_q.columns for col in required):
                    st.session_state.questions_df = df_q
                    st.success(f"{len(df_q)} questions chargées selon votre logique.")
                else:
                    st.error(f"Erreur : Colonnes manquantes. Requis : {', '.join(required)}")

    with tab_json:
        st.subheader("💾 Gestion de la session")
        st.write("Téléchargez ce fichier pour pouvoir reprendre le tournoi exactement là où vous l'avez laissé.")
        st.download_button("📥 Télécharger Sauvegarde (JSON)", export_state_json(), f"tournoi_isep_{datetime.now().strftime('%d%m_%H%M')}.json")
        
        st.divider()
        st.write("Restaurer une session précédente :")
        f_json = st.file_uploader("Importer fichier JSON", type=['json'])
        if f_json and st.button("Valider l'importation"):
            import_state_json(f_json)

# --- PAGE 2 : CALENDRIER ---
elif page == "Calendrier":
    st.title("📅 Calendrier des Rencontres")
    if st.session_state.teams_df.empty:
        st.warning("Veuillez d'abord importer les équipes dans l'onglet Configuration.")
    else:
        teams = sorted(st.session_state.teams_df['Equipe'].unique().tolist())
        if st.button("🚀 Générer les 6 matchs (Tournoi à 9 équipes)"):
            generate_schedule(teams)
            st.success("Calendrier généré !")

        if st.session_state.matches:
            cols = st.columns(3)
            for i, (mid, d) in enumerate(st.session_state.matches.items()):
                with cols[i % 3]:
                    st.info(f"**MATCH {mid}**\n\n{' vs '.join(d['teams'])}\n\nStatut : {d['status']}")

# --- PAGE 3 : ARBITRAGE ---
elif page == "Console d'Arbitrage":
    if not st.session_state.matches:
        st.error("Générez le calendrier d'abord.")
    elif st.session_state.questions_df.empty:
        st.error("Importez le fichier de questions dans l'onglet Configuration.")
    else:
        m_id = st.selectbox("Sélectionner la rencontre", list(st.session_state.matches.keys()), 
                           format_func=lambda x: f"Match {x} : {' / '.join(st.session_state.matches[x]['teams'])}")
        
        m_data = st.session_state.matches[m_id]
        st.markdown(f"<div class='match-header'><h1>MATCH {m_id} : {' vs '.join(m_data['teams'])}</h1></div>", unsafe_allow_html=True)
        
        # Données de la question actuelle
        q_list = st.session_state.questions_df.to_dict(orient='records')
        curr_idx = st.session_state.match_progress[m_id]["q_idx"]
        
        if curr_idx < len(q_list):
            q = q_list[curr_idx]
            
            # Affichage de la phase
            st.subheader(f"📍 {q['Manche']} — {q['Rubrique']}")
            if 'Consigne' in q and pd.notna(q['Consigne']):
                st.markdown(f"<div class='instruction-box'><b>Règles :</b> {q['Consigne']}</div>", unsafe_allow_html=True)
            
            # Affichage de la question
            st.markdown(f"<div class='question-box'><b>Question n°{curr_idx + 1} :</b><br>{q['Question']}</div>", unsafe_allow_html=True)
            
            pts_val = q['Points']
            temps_val = q['Temps']
            
            st.write(f"Points en jeu : **{pts_val}** | Temps imparti : **{temps_val}s**")
            
            c_score, c_nav = st.columns([2, 1])
            with c_score:
                st.write("#### Attribution des points :")
                cols = st.columns(3)
                for i, team in enumerate(m_data['teams']):
                    with cols[i]:
                        st.markdown(f"**{team}**")
                        players = st.session_state.teams_df[st.session_state.teams_df['Equipe'] == team]['Joueur'].tolist()
                        for p in players:
                            if st.button(f"🎯 {p}", key=f"p_{m_id}_{p}_{curr_idx}"):
                                m_data['scores'][team] += int(pts_val)
                                st.session_state.player_scores[p] += int(pts_val)
                                st.toast(f"+{pts_val} pour {p} ({team})")
            
            with c_nav:
                st.write("⏱️ **Chronomètre**")
                if st.button("Lancer le temps"):
                    p_t = st.empty()
                    for s in range(int(temps_val), -1, -1):
                        p_t.metric("Chrono", f"{s}s")
                        time.sleep(1)
                    st.error("FIN DU TEMPS !")
                
                st.divider()
                if st.button("Question Suivante ➡️", type="primary"):
                    st.session_state.match_progress[m_id]["q_idx"] += 1
                    st.rerun()
        else:
            st.success("Toutes les questions ont été posées pour ce match.")

        # Score en direct de la rencontre
        st.divider()
        st.subheader("📊 Tableau des scores")
        sc_cols = st.columns(3)
        for i, t in enumerate(m_data['teams']):
            sc_cols[i].metric(t, f"{m_data['scores'][t]} pts")

        if st.button("🏁 CLÔTURER LE MATCH ET CALCULER LE CLASSEMENT"):
            m_data['status'] = 'Terminé'
            st.success("Match enregistré !")

# --- PAGE 4 : CLASSEMENT ---
elif page == "Classement Général":
    st.title("📊 Classement du Tournoi")
    
    if not st.session_state.teams_df.empty:
        rank_data = {}
        for t in st.session_state.teams_df['Equipe'].unique():
            rank_data[t] = {'Points Tournoi (3-1-0)': 0, 'Total Points Quiz (Diff)': 0}

        for mid, data in st.session_state.matches.items():
            for t, s in data['scores'].items():
                rank_data[t]['Total Points Quiz (Diff)'] += s
            
            if data['status'] == 'Terminé':
                # Tri pour barème 3 pts / 1 pt
                s_m = sorted(data['scores'].items(), key=lambda x: x[1], reverse=True)
                rank_data[s_m[0][0]]['Points Tournoi (3-1-0)'] += 3
                rank_data[s_m[1][0]]['Points Tournoi (3-1-0)'] += 1

        tab_teams, tab_players = st.tabs(["🏆 Equipes", "🥇 Meilleurs Marqueurs"])
        
        with tab_teams:
            df_r = pd.DataFrame.from_dict(rank_data, orient='index').reset_index()
            df_r.columns = ['Équipe', 'Points Match', 'Cumul Quiz']
            df_r = df_r.sort_values(by=['Points Match', 'Cumul Quiz'], ascending=False)
            st.table(df_r)
            st.caption("Barème : 1er = 3 pts | 2ème = 1 pt. Le Cumul Quiz sert à départager les égalités.")

        with tab_players:
            st.subheader("MVP - Classement Individuel")
            p_list = []
            for p, s in st.session_state.player_scores.items():
                t_row = st.session_state.teams_df[st.session_state.teams_df['Joueur'] == p]
                if not t_row.empty:
                    p_list.append({"Joueur": p, "Equipe": t_row['Equipe'].values[0], "Score": s})
            
            if p_list:
                df_p = pd.DataFrame(p_list).sort_values(by="Score", ascending=False)
                st.dataframe(df_p, use_container_width=True, hide_index=True)
                st.success(f"Le meilleur marqueur actuel est **{df_p.iloc[0]['Joueur']}** avec **{df_p.iloc[0]['Score']}** points !")