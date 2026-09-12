"""On-demand explanations, outside the real-time scoring path."""
import re
import numpy as np
from .behavior import FEATURES

class Explainer:
    def __init__(self,cfg,text_layer,behavior_layer):
        self.cfg=cfg; self.text=text_layer; self.behavior=behavior_layer

    def explain(self,transaction,result):
        import shap
        from lime.lime_text import LimeTextExplainer
        f=result['layers']['behavioral']['features']
        values=np.array([[f[k] for k in FEATURES]])
        background=self.behavior.bundle['background']
        explainer=shap.Explainer(self.behavior.predict_array,background,algorithm='permutation',feature_names=FEATURES,seed=self.cfg['seed'])
        explanation=explainer(values,max_evals=2*len(FEATURES)+1)
        base=float(explanation.base_values[0]); contributions=explanation.values[0]
        behavioral=dict(method='SHAP permutation: combined XGBoost + normalized Isolation Forest score',
            units='behavioral risk score',base_value=base,prediction=result['sub_scores']['behavioral'],
            contributions=[dict(feature=k,value=float(f[k]),contribution=float(v)) for k,v in zip(FEATURES,contributions)],
            reconstruction_error=float(abs(base+contributions.sum()-result['sub_scores']['behavioral'])),
            limitation='One seeded permutation cycle and 16 training background rows; correlated features are perturbed independently.')
        text=transaction.text; layer=result['layers']['text']; route=layer['route']
        if route in {'rule_short_circuit','no_text'} or not text or not re.search(r'\w',text):
            text_explanation=dict(method='Exact rule evidence / no model inference',route=route,signals=layer['signals'])
        else:
            def predict(texts):
                p=np.array([self.text.score(t)['score'] for t in texts])
                return np.column_stack([1-p,p])
            lime=LimeTextExplainer(class_names=['legitimate','scam'],random_state=self.cfg['seed'])
            local=lime.explain_instance(text,predict,labels=(1,),num_features=self.cfg['explain']['top_features'],num_samples=self.cfg['explain']['lime_samples'])
            text_explanation=dict(method='LIME over the complete routed text risk function',route=route,
                 contributions=[dict(token=k,contribution=float(v)) for k,v in local.as_list(label=1)],
                 local_fidelity_r2=float(local.score),local_prediction=float(local.local_pred[0]),
                 actual_prediction=layer['score'],signals=layer['signals'],
                 limitation='Local surrogate, not causal evidence; routing can change under token removal. Low R² means unreliable token attribution.')
        return dict(transaction_id=transaction.transaction_id,model_version=result['model_version'],reasons=result['reasons'],
            methods={'behavioral':behavioral,'text':text_explanation,
                     'network':dict(method='Exact transparent formula; maximum of named components',**result['layers']['network']),
                     'fusion':dict(method='Exact weighted contributions relative to zero plus rule override',**result['fusion'])})
