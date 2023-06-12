import json
import pandas as pd
import streamlit as st
import plotly.express as px
from PIL import Image
from pymongo import MongoClient
from py2neo import Graph, Node
from streamlit_agraph import agraph, Node, Edge, Config
from faker import Faker
from datetime import datetime


# ---- READ LOGO ----
image = Image.open("img/logo_blu.png")

# ---- SETTINGS PAGE ----
st.set_page_config(page_title="Dashboard Patient - Healthcare Summarization", page_icon="🩺", layout="wide")

# ---- RETRIEVE MONGO STRING
with open("secrets.json") as f:
    secrets = json.load(f)
    mongo_string = secrets["mongo_string"]

# ---- CONFIGURAZIONE PER AGRAPH
config = Config(width=750,
                height=600,
                directed=True,
                physics={"barnesHut": {"gravitationalConstant": -5000, "centralGravity": 0.3, "springLength": 95, "springConstant": 0.04, "damping": 0.09, "avoidOverlap": 0.1}},
                hierarchical=False
                )


# ---- CONNESSIONE A MONGODB ----
st.cache_data()
def get_summaries():
    ## CONNESSIONE A MONGO ATLAS
    client = MongoClient(mongo_string)

    db = client.noteevents
    summaries = db.summaries_db

    summaries_df = pd.DataFrame(list(summaries.find()))

    return summaries_df

st.cache_data()
def get_noteevents(paziente_id):
    ## CONNESSIONE A MONGO ATLAS
    client = MongoClient(mongo_string)

    db = client.noteevents
    noteevents = db.noteevents_db

    noteevents_df = pd.DataFrame(list(noteevents.find({'SUBJECT_ID': paziente_id})))

    return noteevents_df

summaries_df = get_summaries()

# ---- CONNESSIONE A NEO4J ----
st.cache_data()
def connect_Neo4J():

    graph = Graph("bolt://localhost:7687", user="neo4j", password="bigdata2023")

    graph_re = Graph("bolt://localhost:7687", name="relationextraction", user="neo4j", password="bigdata2023")

    return graph,graph_re

graph,graph_re = connect_Neo4J()


# ---- SIDE BAR ----
#st.sidebar.image(image, width=100)
st.sidebar.title('🩺 Healthcare summarization')
st.sidebar.caption("Transforming complex clinical notes data into __concise__ and __informative__ insights.")
st.sidebar.divider()

# Seleziona paziente
paziente_id = st.sidebar.selectbox(label='Select __patient__ n°: ', options=summaries_df['SUBJECT_ID'])

noteevents_df = get_noteevents(paziente_id)
noteevents_df = noteevents_df.sort_values('CHARTDATE', ascending=True)
st.sidebar.caption("The __patient names__ in the clinical notes of the MIMIC-III dataset are __completely randomized__, ensuring anonymity.")

# ---- MAINPAGE ----
# Estrazione nome e cognome
fake = Faker()
gender = noteevents_df['GENDER'].head(1).to_string(index=False)

if gender == "M":
    first_name = fake.first_name_male()
    last_name = fake.last_name_male()
    gender_sign = "male_sign"
elif gender == "F":
    first_name = fake.first_name_female()
    last_name = fake.last_name_female()
    gender_sign = "female_sign"
else:
    first_name = "Name"
    last_name = "Unknown"

name = ":red[" + first_name + "]"
lastname = last_name

# Titolo della pagina
st.subheader(":blue[DASHBOARD OF] ")
st.title("{} {} :{}:".format(name, lastname, gender_sign))
st.caption("Patient n°: {}".format(paziente_id))

# Analytics demografiche e cliniche sul paziente selezionato
l1, c1, r1 = st.columns(3)
with l1:
    dob = noteevents_df['DOB'].head(1).to_string(index=False)
    dob = datetime.strptime(dob, "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y")
    st.metric(label="📆 Date of birth", value=dob, delta="")

with c1:
    chartdate = noteevents_df['CHARTDATE'].tail(1).to_string(index=False)
    chartdate = datetime.strptime(chartdate, "%Y-%m-%d").strftime("%d-%m-%Y")
    st.metric(label="🏥 Last hospital admission", value=chartdate, delta="")

with r1:
    num_note = str(noteevents_df.shape[0])
    st.metric(label="📝 Number of clinical notes present", value=num_note, delta="")

expired_flag = noteevents_df['EXPIRE_FLAG'].head(1).to_string(index=False)
if expired_flag == "1":
    dod = noteevents_df['DOD'].head(1).to_string(index=False)
    dod = datetime.strptime(dod, "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y")
    st.metric(label="Date of death", value=dod, delta="")


# Extraction Clinical Trend
clinical_trend = summaries_df[summaries_df['SUBJECT_ID'] == paziente_id]['CLINICAL TREND']
clinical_trend_text = ' '.join(clinical_trend.tolist())

if clinical_trend_text in ['Improvement']:
    delta = 1
elif clinical_trend_text in ['Worsening', 'Dead']:
    delta = -1
else:
    delta = 0  # Se il valore non corrisponde a nessuna delle condizioni precedenti

with st.expander("Discover current clinical trends for medical insights and updates", expanded=True):
    st.metric(label=":chart_with_upwards_trend: Clinical Trend", value=clinical_trend_text, delta=delta)

# Extraction Summary
summary = summaries_df[summaries_df['SUBJECT_ID'] == paziente_id]['SUMMARY']
summary_text = ' '.join(summary.tolist())

with st.expander(":page_with_curl: __Summary__ - Concise overview highlighting key findings and important medical information", expanded=True):
    st.write(summary_text)

st.divider()

# --- ANALYTICS ---
st.subheader("Visualizing Patient's Symptom and Disease Count Temporal")
st.caption("Insights into Health Condition between notes of the Patient " + name + " " + lastname)

count_note = []
for index, row in noteevents_df.iterrows():
    note = row['ROW_ID']
    date = row['CHARTDATE']
    result = graph_re.run(f"""
    MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(disease:`Disease or Syndrome`)
    WHERE p.subject_id = {paziente_id} AND n.note_clinical_id = {note}
    RETURN count(disease) AS totalOccurrences
    """)

    for record in result:
        disease_count = str(record)

    result = graph_re.run(f"""
    MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(disease:`Disease or Syndrome`)-[]-(s:`Sign or Symptom`)
    WHERE p.subject_id = {paziente_id} AND n.note_clinical_id = {note}
    RETURN count(s) AS totalOccurrences
    """)

    for record in result:
        symptom_count = str(record)
    
    count_note.append((note,date,disease_count,symptom_count))

count_note_df = pd.DataFrame(count_note, columns=['Note','Date','Disease_Count','Symptom_Count'])
count_note_df['Disease_Count'] = count_note_df['Disease_Count'].astype(int)
count_note_df['Symptom_Count'] = count_note_df['Symptom_Count'].astype(int)
count_note_df = count_note_df.sort_values('Date')

fig = px.line(count_note_df, x='Date', y=['Disease_Count','Symptom_Count'], title='📈 Number of diseases/symptoms diagnosed over time')
st.plotly_chart(fig)

st.divider()

count_procedure = []
for index, row in noteevents_df.iterrows():
    note = row['ROW_ID']
    date = row['CHARTDATE']
    result = graph.run(f"""
    MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(t:`Therapeutic or Preventive Procedure`)
    WHERE p.subject_id = {paziente_id} AND n.note_clinical_id = {note}
    RETURN count(t) AS totalOccurrences
    """)

    for record in result:
        therapeutic_count = str(record)

    result = graph.run(f"""
    MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(l:`Laboratory Procedure`)
    WHERE p.subject_id = {paziente_id} AND n.note_clinical_id = {note}
    RETURN count(l) AS totalOccurrences
    """)

    for record in result:
        laboratory_count = str(record)
    
    count_procedure.append((note,date,therapeutic_count,laboratory_count))

count_procedure_df = pd.DataFrame(count_procedure, columns=['Note','Date','Therapeutic_Procedure_Count','Laboratory_Procedure_Count'])
count_procedure_df['Therapeutic_Procedure_Count'] = count_procedure_df['Therapeutic_Procedure_Count'].astype(int)
count_procedure_df['Laboratory_Procedure_Count'] = count_procedure_df['Laboratory_Procedure_Count'].astype(int)
count_procedure_df = count_procedure_df.sort_values('Date')

fig = px.bar(count_procedure_df, x='Date', y=['Therapeutic_Procedure_Count','Laboratory_Procedure_Count'], barmode='group', title='📊 Number of therapeutic/laboratory procedure diagnosed over time')
st.plotly_chart(fig)

st.divider()


# Lists
st.subheader("⚕️ Explore list drugs, symptoms, and diagnostics of " + name + " " + lastname)
st.caption("Explore __extracted__ drug, symptom, and diagnostic procedure lists from patient's clinical notes: ")


col1, col2, col3 = st.columns(3)

result_pharm = graph_re.run(f"""
MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(d:`Disease or Syndrome`)-[]-(ps:`Pharmacologic Substance`)
WHERE p.subject_id = {paziente_id} AND ps.name <> " " AND NOT (toLower(ps.name) CONTAINS "nan")
return DISTINCT(ps) AS Drugs
""")

drugs = []
for record in result_pharm:
    drug = record[0]
    drugs.append(drug['name'])

drugs = pd.DataFrame(drugs, columns=['Drugs'])
col1.metric("💊 List of Drugs", value="")
col1.dataframe(drugs, hide_index=True, use_container_width=True)

result_symp = graph_re.run(f"""
MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(d:`Disease or Syndrome`)-[]-(s:`Sign or Symptom`)
WHERE p.subject_id = {paziente_id} AND s.name <> " " AND NOT (toLower(s.name) CONTAINS "nan")
return DISTINCT(s) AS Symptoms
""")

symptoms = []
for record in result_symp:
    symptom = record[0]
    symptoms.append(symptom['name'])

symptoms = pd.DataFrame(symptoms, columns=['Symptoms'])
col2.metric("🦠 List of Sign or Symptoms", value="")
col2.dataframe(symptoms, hide_index=True, use_container_width=True)


result_proc = graph_re.run(f"""
MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(d:`Disease or Syndrome`)-[]-(dp:`Diagnostic Procedure`)
WHERE p.subject_id = {paziente_id} AND dp.name <> " " AND NOT (toLower(dp.name) CONTAINS "nan")
return DISTINCT(dp) AS Symptoms
""")

procedures = []
for record in result_proc:
    procedure = record[0]
    procedures.append(procedure['name'])

procedures = pd.DataFrame(procedures, columns=['Diagnostic Procedure'])
col3.metric("🩺 List of Diagnostic Procedure", value="")
col3.dataframe(procedures, hide_index=True, use_container_width=True)


# Analytics visualizzate come grafi
# ----
st.divider()
st.subheader("⚕️ Patient " + name + " " + lastname + " Graph Analysis for insights")
st.caption("Analyze patient's health data through interactive graph visualizations for comprehensive insights: ")



result1 = graph_re.run(f"""
MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(d:`Disease or Syndrome`)
WHERE p.subject_id = {paziente_id}
RETURN p,n,d
""")

nodes = []
edges = []
ids = []
flag = 0
for record in result1:
    flag = 1
    patient_node = record[0]
    if patient_node.identity not in ids:
        ids.append(patient_node.identity)
        nodes.append( Node(id=patient_node.identity, 
                    label=str(patient_node['subject_id']), 
                    size=30,
                    color='red') 
                )
    note_node = record[1]
    if note_node.identity not in ids:
        ids.append(note_node.identity)
        nodes.append( Node(id=note_node.identity, 
                    label=str(note_node['note_clinical_id']), 
                    size=25,
                    color='lightgreen') 
                )
    disease_node = record[2]
    if disease_node.identity not in ids:
        ids.append(disease_node.identity)
        nodes.append( Node(id=disease_node.identity, 
                    label=str(disease_node['name']), 
                    size=20) 
                )    
    edges.append( Edge(source=patient_node.identity, 
                    label="HAS_NOTE", 
                    target=note_node.identity,
                    color='black'
                    ) 
                )
    edges.append( Edge(source=note_node.identity, 
                    label="HAS_DISEASE", 
                    target=disease_node.identity,
                    color='black'
                    ) 
                )

with st.expander("__The diseases associated with each patient's clinical note__", expanded=True):
    if flag == 1:
        st.caption('LEGEND COLOR: __:red[PATIENTS]__ - __:green[CLINICAL NOTE]__ - __:blue[DISEASE OR SINDROME]__ ')
        agraph(nodes=nodes, 
               edges=edges, 
               config=config)
    else:
        st.caption("There are no diseases associated with this patient.")

# ----
result2 = graph.run(f"""
MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]->(b:`Body Part`)
WHERE p.subject_id = {paziente_id} 
RETURN p,b,n
""")

nodes = []
edges = []
ids = []
flag = 0
for record in result2:
    flag = 1
    patient_node = record[0]
    if patient_node.identity not in ids:
        ids.append(patient_node.identity)
        nodes.append( Node(id=patient_node.identity, 
                    label=str(patient_node['subject_id']), 
                    size=30,
                    color='red') 
                )
    body_node = record[1]
    if body_node.identity not in ids:
        ids.append(body_node.identity)
        nodes.append( Node(id=body_node.identity, 
                    label=str(body_node['name']), 
                    size=25) 
                )
    note_node = record[2]
    if note_node.identity not in ids:
        ids.append(note_node.identity)
        nodes.append( Node(id=note_node.identity, 
                    label=str(note_node['note_clinical_id']), 
                    size=25,
                    color='lightgreen') 
                )
    edges.append( Edge(source=patient_node.identity, 
                    label="HAS_NOTE", 
                    target=note_node.identity,
                    color='black'
                    ) 
                )
    edges.append( Edge(source=note_node.identity, 
                    label="HAS_BODY_PART", 
                    target=body_node.identity,
                    color='black'
                    ) 
                )

with st.expander("__The painful body parts associated with each patient's clinical note__", expanded=True):
    if flag == 1:
        st.caption("LEGEND COLOR: __:red[PATIENTS]__ - __:green[CLINICAL NOTE]__ - __:blue[BODY PART]__ ")
        agraph(nodes=nodes, 
               edges=edges, 
               config=config)
    else:
        st.caption("There are no painful body parts associated with this patient.")

# ----
result3 = graph_re.run(f"""
MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(d:`Disease or Syndrome`)-[]-(ps:`Pharmacologic Substance`)
WHERE p.subject_id = {paziente_id}
RETURN p,n,d,ps
""")

nodes = []
edges = []
ids = []
flag = 0
for record in result3:
    flag = 1
    patient_node = record[0]
    if patient_node.identity not in ids:
        ids.append(patient_node.identity)
        nodes.append( Node(id=patient_node.identity, 
                    label=str(patient_node['subject_id']), 
                    size=30,
                    color='red') 
                )
    note_node = record[1]
    if note_node.identity not in ids:
        ids.append(note_node.identity)
        nodes.append( Node(id=note_node.identity, 
                    label=str(note_node['note_clinical_id']), 
                    size=25,
                    color='lightgreen') 
                )
    disease_node = record[2]
    if disease_node.identity not in ids:
        ids.append(disease_node.identity)
        nodes.append( Node(id=disease_node.identity, 
                    label=str(disease_node['name']), 
                    size=25
                    ) 
                )
    pharmacological_node = record[3]
    if pharmacological_node.identity not in ids:
        ids.append(pharmacological_node.identity)
        nodes.append( Node(id=pharmacological_node.identity, 
                    label=str(pharmacological_node['name']), 
                    size=25,
                    color='orange') 
                )
    edges.append( Edge(source=patient_node.identity, 
                    label="HAS_NOTE", 
                    target=note_node.identity,
                    color='black'
                    ) 
                )
    edges.append( Edge(source=note_node.identity, 
                    label="HAS_DISEASE", 
                    target=disease_node.identity,
                    color='black'
                    ) 
                )
    edges.append( Edge(source=pharmacological_node.identity, 
                    label="TREATS", 
                    target=disease_node.identity,
                    color='black'
                    ) 
                )

with st.expander("__The pharmacological substances taken by the patient for each disease diagnosed in his clinical notes__", expanded=True):
    if flag == 1:
        st.caption("LEGEND COLOR: __:red[PATIENTS]__ - __:green[CLINICAL NOTE]__ - __:blue[DISEASE OR SINDROME]__ - __:orange[TREATS]__")
        agraph(nodes=nodes, 
               edges=edges, 
               config=config)
    else:
        st.caption("There are no drugs associated with this patient's diseases.")

# ----
result4 = graph_re.run(f"""
MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(d:`Disease or Syndrome`)-[]-(s:`Sign or Symptom`)
WHERE p.subject_id = {paziente_id}
RETURN p,n,d,s
""")

nodes = []
edges = []
ids = []
flag = 0
for record in result4:
    flag = 1
    patient_node = record[0]
    if patient_node.identity not in ids:
        ids.append(patient_node.identity)
        nodes.append( Node(id=patient_node.identity, 
                    label=str(patient_node['subject_id']), 
                    size=25,
                    color='red') 
                )
    note_node = record[1]
    if note_node.identity not in ids:
        ids.append(note_node.identity)
        nodes.append( Node(id=note_node.identity, 
                    label=str(note_node['note_clinical_id']), 
                    size=25,
                    color='lightgreen') 
                )
    disease_node = record[2]
    if disease_node.identity not in ids:
        ids.append(disease_node.identity)
        nodes.append( Node(id=disease_node.identity, 
                    label=str(disease_node['name']), 
                    size=25
                    ) 
                )
    symptom_node = record[3]
    if symptom_node.identity not in ids:
        ids.append(symptom_node.identity)
        nodes.append( Node(id=symptom_node.identity, 
                    label=str(symptom_node['name']), 
                    size=25,
                    color='orange') 
                )
    edges.append( Edge(source=patient_node.identity, 
                    label="HAS_NOTE", 
                    target=note_node.identity,
                    color='black'
                    ) 
                )
    edges.append( Edge(source=note_node.identity, 
                    label="HAS_DISEASE", 
                    target=disease_node.identity,
                    color='black'
                    ) 
                )
    edges.append( Edge(source=symptom_node.identity, 
                    label="MAY_CAUSE", 
                    target=disease_node.identity,
                    color='black'
                    ) 
                )

with st.expander("__The symptoms presented by the patient for each disease diagnosed in his clinical notes__", expanded=True):
    if flag == 1:
        st.caption("LEGEND COLOR: __:red[PATIENTS]__ - __:green[CLINICAL NOTE]__ - __:blue[DISEASE OR SINDROME]__ - __:orange[SIGN OR SYMPTOMS]__")
        agraph(nodes=nodes, 
               edges=edges, 
               config=config)
    else:
        st.caption("There are no symptoms associated with this patient's diseases.")

# ----
result5 = graph_re.run(f"""
MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(d:`Disease or Syndrome`)-[]-(dp:`Diagnostic Procedure`)
WHERE p.subject_id = {paziente_id}
RETURN p,n,d,dp
""")

nodes = []
edges = []
ids = []
flag = 0
for record in result5:
    flag = 1
    patient_node = record[0]
    if patient_node.identity not in ids:
        ids.append(patient_node.identity)
        nodes.append( Node(id=patient_node.identity, 
                    label=str(patient_node['subject_id']), 
                    size=30,
                    color='red') 
                )
    note_node = record[1]
    if note_node.identity not in ids:
        ids.append(note_node.identity)
        nodes.append( Node(id=note_node.identity, 
                    label=str(note_node['note_clinical_id']), 
                    size=25,
                    color='green') 
                )
    disease_node = record[2]
    if disease_node.identity not in ids:
        ids.append(disease_node.identity)
        nodes.append( Node(id=disease_node.identity, 
                    label=str(disease_node['name']), 
                    size=25) 
                )
    procedure_node = record[3]
    if procedure_node.identity not in ids:
        ids.append(procedure_node.identity)
        nodes.append( Node(id=procedure_node.identity, 
                    label=str(procedure_node['name']), 
                    size=25,
                    color='orange') 
                )
    edges.append( Edge(source=patient_node.identity, 
                    label="HAS_NOTE", 
                    target=note_node.identity,
                    color='black'
                    ) 
                )
    edges.append( Edge(source=note_node.identity, 
                    label="HAS_DISEASE", 
                    target=disease_node.identity,
                    color='black'
                    ) 
                )
    edges.append( Edge(source=procedure_node.identity, 
                    label="DIAGNOSTICS", 
                    target=disease_node.identity,
                    color='black'
                    ) 
                )

with st.expander("__The diagnostic procedures performed on the patient for each disease diagnosed in his clinical notes__", expanded=True):
    if flag == 1:
        st.caption("LEGEND COLOR: __:red[PATIENTS]__ - __:green[CLINICAL NOTE]__ - __:blue[DISEASE OR SINDROME]__ - __:orange[DIAGNOSTIC PROCEDURE]__")
        agraph(nodes=nodes, 
               edges=edges, 
               config=config)
    else:
        st.caption("There are no diagnostic procedures associated with this patient's diseases.")

# ----
result6 = graph_re.run(f"""
MATCH (p:Patient)-[]-(n:`Note Clinical`)-[]-(d:`Disease or Syndrome`)-[]-(l:`Laboratory or Test Result`)
WHERE p.subject_id = {paziente_id}
RETURN p,n,d,l
""")

nodes = []
edges = []
ids = []
flag = 0
for record in result6:
    flag = 1
    patient_node = record[0]
    if patient_node.identity not in ids:
        ids.append(patient_node.identity)
        nodes.append( Node(id=patient_node.identity,
                    label=str(patient_node['subject_id']),
                    size=30,
                    color='red') 
                )
    note_node = record[1]
    if note_node.identity not in ids:
        ids.append(note_node.identity)
        nodes.append( Node(id=note_node.identity,
                    label=str(note_node['note_clinical_id']),
                    size=25,
                    color='lightgreen') 
                )
    disease_node = record[2]
    if disease_node.identity not in ids:
        ids.append(disease_node.identity)
        nodes.append( Node(id=disease_node.identity, 
                    label=str(disease_node['name']), 
                    size=25) 
                )
    test_node = record[3]
    if test_node.identity not in ids:
        ids.append(test_node.identity)
        nodes.append( Node(id=test_node.identity, 
                    label=str(test_node['name']), 
                    size=25,
                    color='pink') 
                )
    edges.append( Edge(source=patient_node.identity,
                    label="HAS_NOTE",
                    target=note_node.identity,
                    color='black'
                    )
                )
    edges.append( Edge(source=note_node.identity, 
                    label="HAS_DISEASE", 
                    target=disease_node.identity,
                    color='black'
                    ) 
                )
    edges.append( Edge(source=test_node.identity, 
                    label="TESTS", 
                    target=disease_node.identity,
                    color='black'
                    ) 
                )

with st.expander("__Laboratory tests performed on the patient for each disease diagnosed in his clinical notes__", expanded=True):
    if flag == 1:
        st.caption("LEGEND COLOR: __:red[PATIENTS]__ - __:green[CLINICAL NOTE]__ - __:blue[DISEASE OR SINDROME]__ - __:pink[TEST]__ ")
        agraph(nodes=nodes, 
               edges=edges, 
               config=config)
    else:
        st.caption("There are no laboratory tests associated with this patient's diseases.")

st.caption("Copyright © 2023 - Progetto 'Healthcare Summarization' realizzato in occasione dell'esame di Big Data Engineering tenuto all'Università degli studi di Napoli, Federico II. Realizzato per soli scopi dimostrativi e didattici. By Antonio Romano, Giuseppe Riccio, Michele Cirillo, Andriy Korsun")

# ---- HIDE STREAMLIT STYLE ----
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)