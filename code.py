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
    .match-header-manual { background: linear-gradient(90deg, #7c3aed 0%, #a78bfa 100%); color: white; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .question-box { background-color: #fffbeb; border-left: 5px solid #f59e0b; padding: 15px; border-radius: 10px; margin: 10px 0; font-size: 1.2em; border: 1px solid #fef3c7; }
    .instruction-box { background-color: #eff6ff; border-left: 5px solid #3b82f6; padding: 15px; border-radius: 8px; font-style: italic; margin-bottom: 15px; color: #1e40af; }
    .format-info { background-color: #f0fdf4; border: 1px solid #16a34a; padding: 10px; border-radius: 5px; margin-bottom: 20px; }
    .manual-badge { background-color: #7c3aed; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; font-weight: bold; margin-left: 8px; }
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
    if 'manual_match_counter' not in st.session_state:
        st.session_state.manual_match_counter = 0
    if 'nb_teams_choice' not in st.session_state:
        st.session_state.nb_teams_choice = 2

init_session()

# --- PERSISTENCE ---
def export_state_json():
    state = {
        "teams": st.session_state.teams_df.to_dict(orient='records'),
        "questions": st.session_state.questions_df.to_dict(orient='records'),
        "matches": st.session_state.matches,
        "player_scores": st.session_state.player_scores,
        "match_progress": st.session_state.match_progress,
        "manual_match_counter": st.session_state.manual_match_counter
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
        st.session_state.manual_match_counter = data.get("manual_match_counter", 0)
        st.success("Session restaurée avec succès !")
        st.rerun()
    except Exception as e:
        st.error(f"Erreur de lecture du fichier JSON : {e}")

# --- LOGIQUE TOURNOI ---
def generate_schedule(teams):
    if len(teams) != 9:
        st.error(f"Le tournoi nécessite exactement 9 équipes (actuellement {len(teams)}).")
        return
    indices = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8]]
    matches = {}
    for i, grp in enumerate(indices):
        mid = str(i+1)
        m_teams = [teams[j] for j in grp]
        matches[mid] = {'teams': m_teams, 'scores': {t: 0 for t in m_teams}, 'status': 'Prévu', 'type': 'auto'}
        st.session_state.match_progress[mid] = {"q_idx": 0}
    st.session_state.matches = matches

# --- CRÉATION D'UN MATCH MANUEL ---
def create_manual_match(selected_teams, match_label):
    """Crée un match manuel avec 2 ou 3 équipes sélectionnées."""
    if len(selected_teams) < 2 or len(selected_teams) > 3:
        return False, "Sélectionnez 2 ou 3 équipes pour le match."
    if len(set(selected_teams)) != len(selected_teams):
        return False, "Chaque équipe ne peut apparaître qu'une seule fois."

    st.session_state.manual_match_counter += 1
    mid = f"M{st.session_state.manual_match_counter}"

    label = match_label.strip() if match_label.strip() else f"Match Manuel {st.session_state.manual_match_counter}"

    st.session_state.matches[mid] = {
        'teams': selected_teams,
        'scores': {t: 0 for t in selected_teams},
        'status': 'Prévu',
        'type': 'manuel',
        'label': label
    }
    st.session_state.match_progress[mid] = {"q_idx": 0}
    return True, mid

# --- SUPPRESSION D'UN MATCH MANUEL ---
def delete_manual_match(mid):
    """Supprime un match manuel (uniquement si non terminé)."""
    if mid in st.session_state.matches:
        match = st.session_state.matches[mid]
        if match.get('type') == 'manuel' and match['status'] != 'Terminé':
            del st.session_state.matches[mid]
            if mid in st.session_state.match_progress:
                del st.session_state.match_progress[mid]
            return True
    return False

# --- CALCUL DES POINTS DE MATCH AVEC GESTION DES ÉGALITÉS ---
def compute_match_points(scores):
    """
    Règles :
      - 1 seul vainqueur          → 3 pts, 2ème → 1 pt, 3ème → 0 pt
      - Égalité 1ère place (2 éq) → 1 pt chacune, 3ème → 0 pt
      - Égalité 1ère place (3 éq) → 1 pt chacune
      - 2ème et 3ème à égalité    → 1 pt chacune, 1er → 3 pts
    Retourne un dict {equipe: points_match}
    """
    result = {t: 0 for t in scores}
    sorted_scores = sorted(set(scores.values()), reverse=True)

    rank1_score = sorted_scores[0]
    rank1_teams = [t for t, s in scores.items() if s == rank1_score]

    if len(rank1_teams) >= 2:
        for t in rank1_teams:
            result[t] = 1
        return result

    winner = rank1_teams[0]
    result[winner] = 3

    if len(sorted_scores) >= 2:
        rank2_score = sorted_scores[1]
        rank2_teams = [t for t, s in scores.items() if s == rank2_score]
        for t in rank2_teams:
            result[t] = 1

    return result

def get_match_display_name(mid, data):
    """Retourne le nom d'affichage d'un match."""
    label = data.get('label', '')
    teams_str = ' / '.join(data['teams'])
    badge = " [MANUEL]" if data.get('type') == 'manuel' else ""
    if label:
        return f"Match {mid} — {label} : {teams_str}{badge}"
    return f"Match {mid} : {teams_str}{badge}"

# --- NAVIGATION ---
st.sidebar.title("🏆 Tournament Manager")
page = st.sidebar.radio("Navigation", [
    "Configuration & Sauvegarde",
    "Calendrier",
    "Matchs Manuels",
    "Console d'Arbitrage",
    "Classement Général"
])

# --- PAGE 1 : SETUP ---
if page == "Configuration & Sauvegarde":
    st.title("📂 Paramètres du Tournoi")

    tab_import, tab_json = st.tabs(["📥 Importation des Fichiers", "💾 Sauvegarde JSON"])

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
            f_teams = st.file_uploader("Fichier Equipes (CSV/XLSX)", type=['csv', 'xlsx'])
            if f_teams:
                df = pd.read_csv(f_teams, sep=None, engine='python') if f_teams.name.endswith('.csv') else pd.read_excel(f_teams)
                st.session_state.teams_df = df
                for p in df['Joueur'].unique():
                    if p not in st.session_state.player_scores: st.session_state.player_scores[p] = 0
                st.success(f"{len(df['Equipe'].unique())} équipes chargées.")

        with c2:
            st.subheader("❓ Banque de Questions")
            f_q = st.file_uploader("Fichier Questions (Format Imposé)", type=['csv', 'xlsx'])
            if f_q:
                df_q = pd.read_csv(f_q, sep=None, engine='python') if f_q.name.endswith('.csv') else pd.read_excel(f_q)
                required = ['Manche', 'Rubrique', 'Question', 'Points', 'Temps']
                if all(col in df_q.columns for col in required):
                    st.session_state.questions_df = df_q
                    st.success(f"{len(df_q)} questions chargées.")
                else:
                    st.error(f"Colonnes manquantes. Requis : {', '.join(required)}")

    with tab_json:
        st.subheader("💾 Gestion de la session")
        st.download_button("📥 Exporter Sauvegarde (JSON)", export_state_json(), f"tournoi_save_{datetime.now().strftime('%d%m_%H%M')}.json")
        st.divider()
        f_json = st.file_uploader("Restaurer fichier JSON", type=['json'])
        if f_json and st.button("Valider l'importation"):
            import_state_json(f_json)

# --- PAGE 2 : CALENDRIER ---
elif page == "Calendrier":
    st.title("📅 Calendrier")
    if st.session_state.teams_df.empty:
        st.warning("Veuillez d'abord importer les équipes.")
    else:
        teams = sorted(st.session_state.teams_df['Equipe'].unique().tolist())
        if st.button("🚀 Générer les 6 matchs automatiques"):
            generate_schedule(teams)
            st.success("Calendrier généré !")

        if st.session_state.matches:
            auto_matches = {mid: d for mid, d in st.session_state.matches.items() if d.get('type', 'auto') == 'auto'}
            manual_matches = {mid: d for mid, d in st.session_state.matches.items() if d.get('type') == 'manuel'}

            if auto_matches:
                st.subheader("🔵 Matchs du Calendrier")
                cols = st.columns(3)
                for i, (mid, d) in enumerate(auto_matches.items()):
                    with cols[i % 3]:
                        status_color = "✅" if d['status'] == 'Terminé' else "⏳"
                        st.info(f"**MATCH {mid}** {status_color}\n\n{' vs '.join(d['teams'])}\n\nStatut : {d['status']}")

            if manual_matches:
                st.subheader("🟣 Matchs Manuels")
                cols = st.columns(3)
                for i, (mid, d) in enumerate(manual_matches.items()):
                    with cols[i % 3]:
                        status_color = "✅" if d['status'] == 'Terminé' else "⏳"
                        label = d.get('label', mid)
                        st.info(f"**{label}** [{mid}] {status_color}\n\n{' vs '.join(d['teams'])}\n\nStatut : {d['status']}")

# --- PAGE 3 : MATCHS MANUELS ---
elif page == "Matchs Manuels":
    st.title("🟣 Gestion des Matchs Manuels")

    if st.session_state.teams_df.empty:
        st.warning("Veuillez d'abord importer les équipes.")
    else:
        teams_list = sorted(st.session_state.teams_df['Equipe'].unique().tolist())

        st.markdown("""
        <div class='format-info'>
        <b>ℹ️ Les matchs manuels comptent dans le classement général</b> (Points Match + Total Quiz) exactement comme les matchs du calendrier automatique.
        </div>
        """, unsafe_allow_html=True)

        st.subheader("➕ Créer un nouveau match")

        # --- Choix du nombre d'équipes HORS du form pour que les selectbox se mettent à jour dynamiquement ---
        col_label, col_nb = st.columns([2, 1])
        with col_label:
            match_label = st.text_input(
                "Nom du match (optionnel)",
                placeholder="Ex : Finale, Demi-finale A, Match de barrage...",
                key="match_label_input"
            )
        with col_nb:
            nb_teams = st.radio(
                "Nombre d'équipes",
                [2, 3],
                horizontal=True,
                key="nb_teams_radio"
            )

        # --- Selectbox dynamiques selon nb_teams, avec clé incluant nb_teams ---
        team_options = ["— Choisir —"] + teams_list
        st.write(f"**Sélectionner {nb_teams} équipes :**")
        team_cols = st.columns(nb_teams)
        selected = []

        for i in range(nb_teams):
            with team_cols[i]:
                choice = st.selectbox(
                    f"Équipe {i+1}",
                    team_options,
                    key=f"team_select_{nb_teams}_{i}"   # ← clé dynamique incluant nb_teams
                )
                selected.append(choice)

        # --- Bouton de création ---
        if st.button("🚀 Créer le match", type="primary", key="create_match_btn"):
            filtered = [t for t in selected if t != "— Choisir —"]
            if len(filtered) < nb_teams:
                st.error(f"Veuillez sélectionner {nb_teams} équipes.")
            elif len(set(filtered)) != len(filtered):
                st.error("Chaque équipe doit être différente.")
            else:
                ok, result = create_manual_match(filtered, match_label)
                if ok:
                    label_display = match_label.strip() if match_label.strip() else result
                    st.success(f"✅ Match **{label_display}** [{result}] créé avec {' vs '.join(filtered)} !")
                    st.rerun()
                else:
                    st.error(result)

        st.divider()

        # --- Liste des matchs manuels existants ---
        manual_matches = {mid: d for mid, d in st.session_state.matches.items() if d.get('type') == 'manuel'}

        if not manual_matches:
            st.info("Aucun match manuel créé pour l'instant.")
        else:
            st.subheader(f"📋 Matchs manuels existants ({len(manual_matches)})")

            for mid, data in manual_matches.items():
                label = data.get('label', mid)
                status = data['status']
                teams_str = ' vs '.join(data['teams'])
                status_icon = "✅" if status == 'Terminé' else "⏳"

                with st.expander(f"{status_icon} **{label}** [{mid}] — {teams_str} — {status}"):
                    col_info, col_scores, col_action = st.columns([2, 2, 1])

                    with col_info:
                        st.write(f"**Équipes :** {teams_str}")
                        st.write(f"**Statut :** {status}")
                        st.write(f"**Format :** {len(data['teams'])} équipes")

                    with col_scores:
                        if status == 'Terminé':
                            st.write("**Scores finaux :**")
                            for t, s in data['scores'].items():
                                st.write(f"• {t} : {s} pts")
                            mp = compute_match_points(data['scores'])
                            st.write("**Points match attribués :**")
                            for t, p in mp.items():
                                st.write(f"• {t} : {p} pts")
                        else:
                            st.write("*Match non encore joué*")

                    with col_action:
                        if status != 'Terminé':
                            if st.button(f"🗑️ Supprimer", key=f"del_{mid}"):
                                if delete_manual_match(mid):
                                    st.success("Match supprimé.")
                                    st.rerun()
                        else:
                            st.write("*(terminé)*")

# --- PAGE 4 : ARBITRAGE ---
elif page == "Console d'Arbitrage":
    if not st.session_state.matches:
        st.error("Générez le calendrier ou créez des matchs manuels d'abord.")
    elif st.session_state.questions_df.empty:
        st.error("Importez les questions d'abord.")
    else:
        available_matches = [mid for mid, data in st.session_state.matches.items() if data['status'] != 'Terminé']

        if not available_matches:
            st.success("🏁 Tous les matchs sont terminés ! Consultez l'onglet 'Classement Général'.")
        else:
            m_id = st.selectbox(
                "Sélectionner la rencontre à arbitrer",
                available_matches,
                format_func=lambda x: get_match_display_name(x, st.session_state.matches[x])
            )

            m_data = st.session_state.matches[m_id]
            is_manual = m_data.get('type') == 'manuel'
            label = m_data.get('label', f"Match {m_id}")
            header_class = "match-header-manual" if is_manual else "match-header"
            badge_text = " 🟣 MANUEL" if is_manual else ""

            st.markdown(
                f"<div class='{header_class}'><h1>{label} [{m_id}]{badge_text} : {' vs '.join(m_data['teams'])}</h1></div>",
                unsafe_allow_html=True
            )

            q_list = st.session_state.questions_df.to_dict(orient='records')
            curr_idx = st.session_state.match_progress[m_id]["q_idx"]

            if curr_idx < len(q_list):
                q = q_list[curr_idx]
                st.subheader(f"📍 {q['Manche']} — {q['Rubrique']}")
                if 'Consigne' in q and pd.notna(q['Consigne']):
                    st.markdown(f"<div class='instruction-box'>{q['Consigne']}</div>", unsafe_allow_html=True)

                st.markdown(f"<div class='question-box'><b>Question n°{curr_idx + 1} :</b><br>{q['Question']}</div>", unsafe_allow_html=True)
                pts_val = q['Points']
                temps_val = q['Temps']
                st.write(f"Points : **{pts_val}** | Temps : **{temps_val}s**")

                c_score, c_nav = st.columns([2, 1])
                with c_score:
                    cols = st.columns(len(m_data['teams']))
                    for i, team in enumerate(m_data['teams']):
                        with cols[i]:
                            st.markdown(f"**{team}**")
                            players = st.session_state.teams_df[st.session_state.teams_df['Equipe'] == team]['Joueur'].tolist()
                            for p in players:
                                if st.button(f"🎯 {p}", key=f"p_{m_id}_{p}_{curr_idx}"):
                                    m_data['scores'][team] += int(pts_val)
                                    st.session_state.player_scores[p] += int(pts_val)
                                    st.toast(f"+{pts_val} pour {p}")

                with c_nav:
                    st.write("⏱️ **Chrono**")
                    if st.button("Lancer"):
                        p_t = st.empty()
                        for s in range(int(temps_val), -1, -1):
                            p_t.metric("Chrono", f"{s}s")
                            time.sleep(1)
                        st.error("FIN !")
                    st.divider()
                    if st.button("Suivant ➡️", type="primary"):
                        st.session_state.match_progress[m_id]["q_idx"] += 1
                        st.rerun()
            else:
                st.success("Questions terminées pour ce match.")

            st.divider()
            sc_cols = st.columns(len(m_data['teams']))
            for i, t in enumerate(m_data['teams']):
                sc_cols[i].metric(t, f"{m_data['scores'][t]} pts")

            if st.button("🏁 TERMINER LE MATCH", type="primary"):
                st.session_state.matches[m_id]['status'] = 'Terminé'
                save_data = export_state_json()
                timestamp = datetime.now().strftime('%d%m_%H%M')
                filename = f"tournoi_save_{timestamp}.json"
                st.success("✅ Match clôturé ! Téléchargez la sauvegarde ci-dessous, puis continuez.")
                st.download_button(
                    label="📥 Télécharger la sauvegarde JSON",
                    data=save_data,
                    file_name=filename,
                    mime="application/json",
                    type="primary"
                )
                st.info("Après le téléchargement, cliquez sur **Actualiser** pour continuer.")
                if st.button("🔄 Actualiser", key=f"refresh_{m_id}"):
                    st.rerun()

# --- PAGE 5 : CLASSEMENT ---
elif page == "Classement Général":
    st.title("📊 Classement Général")

    if not st.session_state.teams_df.empty:
        rank_data = {}
        for t in st.session_state.teams_df['Equipe'].unique():
            rank_data[t] = {'Points Match': 0, 'Total Quiz': 0, 'Matchs Joués': 0}

        for mid, data in st.session_state.matches.items():
            for t, s in data['scores'].items():
                if t in rank_data:
                    rank_data[t]['Total Quiz'] += s

            if data['status'] == 'Terminé':
                match_pts = compute_match_points(data['scores'])
                for t, pts in match_pts.items():
                    if t in rank_data:
                        rank_data[t]['Points Match'] += pts
                        rank_data[t]['Matchs Joués'] += 1

        t_rank, p_rank, detail_tab = st.tabs(["🏆 Équipes", "🥇 Joueurs", "📋 Détail des Matchs"])

        with t_rank:
            df_r = pd.DataFrame.from_dict(rank_data, orient='index').reset_index()
            df_r.columns = ['Équipe', 'Points Match', 'Total Quiz', 'Matchs Joués']
            df_r = df_r.sort_values(by=['Points Match', 'Total Quiz'], ascending=False).reset_index(drop=True)
            df_r.index += 1
            st.table(df_r)

        with p_rank:
            def get_team(player):
                match = st.session_state.teams_df[st.session_state.teams_df['Joueur'] == player]
                return match['Equipe'].values[0] if len(match) > 0 else "—"

            p_list = [
                {"Joueur": p, "Equipe": get_team(p), "Score": s}
                for p, s in st.session_state.player_scores.items()
            ]
            st.dataframe(pd.DataFrame(p_list).sort_values(by="Score", ascending=False), use_container_width=True, hide_index=True)

        with detail_tab:
            st.subheader("Récapitulatif de tous les matchs")
            for mid, data in st.session_state.matches.items():
                match_type = "🟣 Manuel" if data.get('type') == 'manuel' else "🔵 Calendrier"
                label = data.get('label', f"Match {mid}")
                status_icon = "✅" if data['status'] == 'Terminé' else "⏳"
                with st.expander(f"{status_icon} **{label}** [{mid}] — {match_type} — {data['status']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Scores Quiz :**")
                        for t, s in data['scores'].items():
                            st.write(f"• {t} : {s} pts")
                    with col2:
                        if data['status'] == 'Terminé':
                            mp = compute_match_points(data['scores'])
                            st.write("**Points Match :**")
                            for t, p in mp.items():
                                st.write(f"• {t} : {p} pts")
                        else:
                            st.write("*Match non terminé*")
    else:
        st.warning("Veuillez d'abord importer les équipes.")
