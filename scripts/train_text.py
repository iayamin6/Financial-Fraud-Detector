import fraud  # Set native thread limits before importing numerical libraries.
"""Stage 3: train and evaluate baseline and a real pretrained DistilBERT checkpoint."""
import os
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
import random
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report,confusion_matrix
from transformers import AutoTokenizer,AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer
from fraud.config import load_config
from fraud.evaluation import metrics,save_report

cfg=load_config(); seed=cfg['seed']; random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.set_num_threads(4)
path=Path(cfg['paths']['models']); path.mkdir(exist_ok=True)
df=pd.read_csv(Path(cfg['paths']['data'])/'texts.csv'); train=df[df.split=='train']; test=df[df.split=='test']; val=df[df.split=='validation']
classes=['legitimate','otp_scam','phishing','impersonation']; labels={v:i for i,v in enumerate(classes)}
baseline=make_pipeline(TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True),LogisticRegression(C=cfg['nlp']['baseline_C'],max_iter=500,class_weight='balanced',random_state=seed))
baseline.fit(train.text,train.fraud); joblib.dump(baseline,path/'text_baseline.joblib')
save_report(cfg,'text_baseline',metrics(test.fraud,baseline.predict_proba(test.text)[:,1]))
tokenizer=AutoTokenizer.from_pretrained(cfg['nlp']['base_model'])
model=AutoModelForSequenceClassification.from_pretrained(cfg['nlp']['base_model'],num_labels=4,id2label=dict(enumerate(classes)),label2id=labels)
device='mps' if torch.backends.mps.is_available() else 'cpu'; model.to(device)
optimizer=torch.optim.AdamW(model.parameters(),lr=cfg['nlp']['learning_rate'])
best=-1
for epoch in range(cfg['nlp']['epochs']):
    model.train(); loss_total=0
    order=np.random.permutation(len(train))
    for start in range(0,len(train),cfg['nlp']['batch_size']):
        batch=train.iloc[order[start:start+cfg['nlp']['batch_size']]]
        inputs=tokenizer(batch.text.tolist(),padding=True,truncation=True,max_length=cfg['nlp']['max_length'],return_tensors='pt').to(device)
        y=torch.tensor([labels[x] for x in batch.label],device=device)
        optimizer.zero_grad(); output=model(**inputs,labels=y); output.loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
        optimizer.step(); loss_total+=output.loss.item()
    model.eval(); probs=[]
    for start in range(0,len(val),16):
        inputs=tokenizer(val.text.iloc[start:start+16].tolist(),padding=True,truncation=True,max_length=cfg['nlp']['max_length'],return_tensors='pt').to(device)
        with torch.inference_mode(): probs.extend(model(**inputs).logits.softmax(-1).cpu().numpy())
    score=metrics(val.fraud,1-np.asarray(probs)[:,0])['f1']
    print(f'epoch={epoch+1} loss_sum={loss_total:.3f} validation_f1={score:.3f} device={device}',flush=True)
    if score>best:
        best=score; model.save_pretrained(path/'bert'); tokenizer.save_pretrained(path/'bert')
model=AutoModelForSequenceClassification.from_pretrained(path/'bert').to(device).eval(); probs=[]
for start in range(0,len(test),16):
    inputs=tokenizer(test.text.iloc[start:start+16].tolist(),padding=True,truncation=True,max_length=cfg['nlp']['max_length'],return_tensors='pt').to(device)
    with torch.inference_mode(): probs.extend(model(**inputs).logits.softmax(-1).cpu().numpy())
probs=np.asarray(probs)
save_report(cfg,'text_bert',{'binary':metrics(test.fraud,1-probs[:,0]),'multiclass':classification_report([labels[x] for x in test.label],probs.argmax(1),labels=list(range(4)),target_names=classes,output_dict=True,zero_division=0),
 'multiclass_confusion_matrix':confusion_matrix([labels[x] for x in test.label],probs.argmax(1),labels=list(range(4))).tolist(),'class_order':classes,'checkpoint':cfg['nlp']['base_model'],'validation_selection':'best binary F1','device':device})
SentenceTransformer(cfg['nlp']['embedding_model']).save(str(path/'embeddings'))
del model
from fraud.text import TextLayer
layer=TextLayer(cfg)
scores=[layer.score(t)['score'] for t in test.text]
save_report(cfg,'text_layer',metrics(test.fraud,scores))
