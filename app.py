import streamlit as st
import pandas as pd
import requests
import zipfile
import io
from datetime import datetime

st.set_page_config(page_title="COT Istituzionale (Commercials)", layout="wide")
st.title("🏛️ COT Bias Analyzer — Strategia Istituzionale (Commercials)")

@st.cache_data(ttl=3600)
def scarica_storico_cot():
    anno_corrente = datetime.now().year
    anni = [anno_corrente - 2, anno_corrente - 1, anno_corrente]
    lista_df = []
    
    for anno in anni:
        url = f"https://cftc.gov{anno}.zip"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    nome_file = z.namelist()[0]
                    with z.open(nome_file) as f:
                        df_temp = pd.read_csv(f, low_memory=False)
                        df_temp.columns = [c.strip() for c in df_temp.columns]
                        lista_df.append(df_temp)
        except Exception:
            continue
            
    df_completo = pd.concat(lista_df, ignore_index=True)
    df_completo['As of Date in Form YYYY-MM-DD'] = pd.to_datetime(df_completo['As of Date in Form YYYY-MM-DD'])
    df_completo = df_completo.sort_values('As of Date in Form YYYY-MM-DD').drop_duplicates(
        subset=['Market and Exchange Names', 'As of Date in Form YYYY-MM-DD']
    )
    return df_completo

try:
    with st.spinner("Scaricamento storico ufficiale CFTC (ultimi 3 anni)..."):
        df = scarica_storico_cot()
        
    mercati = sorted(df['Market and Exchange Names'].unique())
    default_target = "EURO SHORT TERM RATE - CHICAGO MERCANTILE EXCHANGE"
    default_idx = mercati.index(default_target) if default_target in mercati else 0
    
    mercato_scelto = st.selectbox("Seleziona il contratto Futures:", mercati, index=default_idx)
    
    df_m = df[df['Market and Exchange Names'] == mercato_scelto].copy()
    
    df_m['Net_Commercials'] = df_m['Commercial Positions-Long (All)'] - df_m['Commercial Positions-Short (All)']
    df_m['Net_Speculators'] = df_m['Noncommercial Positions-Long (All)'] - df_m['Noncommercial Positions-Short (All)']
    
    finestra = min(52, len(df_m))
    min_52w = df_m['Net_Commercials'].rolling(finestra).min()
    max_52w = df_m['Net_Commercials'].rolling(finestra).max()
    df_m['COT_Index_52w'] = 100 * (df_m['Net_Commercials'] - min_52w) / (max_52w - min_52w)
    
    ultimo = df_m.iloc[-1]
    penultimo = df_m.iloc[-2] if len(df_m) > 1 else ultimo
    
    cot_idx = ultimo['COT_Index_52w']
    var_comm = ultimo['Net_Commercials'] - penultimo['Net_Commercials']
    
    if cot_idx >= 80:
        bias = "🟢 FORTE BIAS LONG — Le istituzioni sono in massimo accumulo rialzista (COT Index ≥ 80%)"
        azione = "Cercare setup di acquisto (Long) sul grafico alla prima conferma di inversione del prezzo."
    elif cot_idx <= 20:
        bias = "🔴 FORTE BIAS SHORT — Le istituzioni sono in massima copertura ribassista (COT Index ≤ 20%)"
        azione = "Cercare setup di vendita (Short) sul grafico alla prima debolezza del prezzo."
    else:
        bias = "🟡 NEUTRALE — Le istituzioni non sono su livelli estremi"
        azione = "Attendere che le istituzioni raggiungano un estremo (>80% o <20%) prima di esporsi."

    st.subheader(f"Dati ufficiali al: {ultimo['As of Date in Form YYYY-MM-DD'].strftime('%d/%m/%Y')}")
    st.markdown(f"### {bias}")
    st.info(f"**Indicazione operativa:** {azione}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Net Commercials (Istituzioni)", f"{int(ultimo['Net_Commercials']):,}", f"{int(var_comm):,} vs sett. prec.")
    col2.metric("COT Index Istituzionale (52 sett.)", f"{cot_idx:.1f}%" if pd.notna(cot_idx) else "Dati insufficienti")
    col3.metric("Net Non-Commercials (Fondi)", f"{int(ultimo['Net_Speculators']):,}", f"{int(ultimo['Net_Speculators'] - penultimo['Net_Speculators']):,}")
    
    st.divider()
    
    tab1, tab2 = st.tabs(["📈 Posizioni Nette (Istituzioni vs Fondi)", "🎯 COT Index Istituzionale (52 Settimane)"])
    
    with tab1:
        st.line_chart(df_m.set_index('As of Date in Form YYYY-MM-DD')[['Net_Commercials', 'Net_Speculators']])
        
    with tab2:
        st.line_chart(df_m.set_index('As of Date in Form YYYY-MM-DD')[['COT_Index_52w']])
        st.caption("Sopra l'80% indica zona di accumulo istituzionale (Long). Sotto il 20% indica zona di distribuzione istituzionale (Short).")

except Exception as e:
    st.error(f"Errore durante l'elaborazione: {e}")
