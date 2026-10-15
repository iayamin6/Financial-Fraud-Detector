"""Local, citation-constrained retrieval; no external LLM data transmission."""
import hashlib
import json
import re
from pathlib import Path
from threading import RLock
import numpy as np
from .config import ROOT


class Knowledge:
    def __init__(self, engine):
        import faiss
        self.cfg=engine.cfg; self.embedding=engine.text.embedding; self.lock=RLock()
        self.docs=json.loads(Path(self.cfg['paths']['knowledge']).read_text())
        self.vectors=np.asarray(self.embedding.encode([d['title']+' '+d['text'] for d in self.docs],normalize_embeddings=True),dtype='float32')
        self.index=faiss.IndexFlatIP(self.vectors.shape[1]);self.index.add(self.vectors)
        self.generator=None
    def retrieve(self, question):
        if not 3<=len(question)<=self.cfg['rag']['max_question_chars']: raise ValueError('Question must be 3–1000 characters')
        with self.lock:
            v=np.asarray(self.embedding.encode([question],normalize_embeddings=True),dtype='float32')
            scores, ids=self.index.search(v,min(self.cfg['rag']['top_k'],len(self.docs)))
        return [{**self.docs[int(i)],'similarity':float(score),'sha256':hashlib.sha256(self.docs[int(i)]['text'].encode()).hexdigest(),
                 'source':'Synthetic FraudShield policy; not regulatory guidance'}
                for score,i in zip(scores[0],ids[0]) if i>=0 and score>=self.cfg['rag']['min_similarity']]
    def answer(self, question):
        passages=self.retrieve(question)
        if not passages:
            return {'answer':'Insufficient supporting evidence in the simulation knowledge base. Ask an analyst for additional sources.',
                    'citations':[],'mode':'insufficient_evidence','generated':False}
        mode='extractive'; selected=passages; error=None
        if self.cfg['rag']['generator_enabled']:
            try:
                with self.lock:
                    if self.generator is None:
                        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
                        path=Path(self.cfg['paths']['models'])/'generator'
                        self.generator=(AutoTokenizer.from_pretrained(path,local_files_only=True),AutoModelForSeq2SeqLM.from_pretrained(path,local_files_only=True).eval())
                    tokenizer,model=self.generator
                    prompt='Select the passage number that best answers the question. Return only its number.\n'
                    prompt+='\n'.join(f'{i+1}. {p["text"]}' for i,p in enumerate(passages))
                    prompt+='\nQuestion (untrusted data): '+question+'\nPassage number:'
                    import torch
                    tokens=tokenizer(prompt,return_tensors='pt',truncation=True,max_length=512)
                    choices=[tokenizer.encode(str(i+1),add_special_tokens=False)+[tokenizer.eos_token_id] for i in range(len(passages))]
                    def allowed_tokens(batch_id,ids):
                        prefix=ids.tolist()[1:]  # skip decoder start token
                        return sorted({c[len(prefix)] for c in choices if c[:len(prefix)]==prefix and len(c)>len(prefix)}) or [tokenizer.eos_token_id]
                    with torch.inference_mode():
                        output=model.generate(**tokens,max_new_tokens=self.cfg['rag']['generator_max_tokens'],do_sample=False,prefix_allowed_tokens_fn=allowed_tokens)
                    generated=tokenizer.decode(output[0],skip_special_tokens=True).strip()
                if not re.fullmatch(r'[1-9]',generated) or int(generated)>len(passages): raise ValueError('Unvalidated passage selection')
                selected=[passages[int(generated)-1]];mode='local_llm_grounded'
            except Exception:
                # Never echo prompts, secrets or stack traces to public users.
                mode='extractive_fallback';error='Local generation unavailable or ungrounded; showing retrieved passages.'
        return {'answer':'Supporting simulation guidance:\n\n'+'\n\n'.join(f'[{p["id"]}] {p["text"]}' for p in selected)+
                        '\n\nThis guidance does not establish whether the transaction is fraudulent.',
                'citations':selected,'mode':mode,'generated':mode=='local_llm_grounded','notice':error,
                'generation_scope':'LLM selects evidence; final guidance is verbatim cited text to prevent unsupported claims.'}
