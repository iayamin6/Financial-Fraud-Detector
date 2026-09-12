"""Original synthetic fixtures. No PaySim download or claim of real-world validity."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from .config import load_config

# Entire templates are held out, including their augmented variants.
TEMPLATES = {
'legitimate': [
 'Payment of {amount} received from {name}. Thank you.', 'Your balance is {amount}. No action required.',
 'Never share your OTP or PIN. Bank staff will never ask for them.', 'Your grocery order from {name} is confirmed.',
 'Rent for this month is {amount}. Thanks.', 'Your statement is ready in the official banking app.',
 'Transfer to {name} completed successfully.', 'Your one time code is {amount}. Do not disclose it to anyone.',
 'Lunch reimbursement for {name}, amount {amount}.', 'Scheduled utility payment will occur tomorrow.',
 'You changed your password successfully. Contact the official branch if this was not you.', 'Receipt for invoice {amount} from {name}.',
 'Please send the meeting notes to {name} when convenient.', 'Account balance updated after purchase at {name}.',
 'Do not provide your verification code to callers claiming to be agents.', 'The card you reported lost is blocked. Visit your branch for a replacement.',
 'School fees of {amount} have been paid.', 'Your refund from {name} is on its way.',
 'Savings deposit confirmation: {amount} credited.', 'We will meet {name} at the bank tomorrow.'
],
'otp_scam': [
 'Send your OTP to {name} immediately to keep your account active.', 'Share your PIN with the support agent for verification.',
 'Tell us your verification code now or your transfer will fail.', 'Reply with your password to unlock your wallet.',
 'Provide your OTP so we can reverse the charge of {amount}.', 'Give the agent your security code to receive your refund.',
 'Forward your OTP to this number for account validation.', 'Send the PIN here to cancel the suspicious transfer.',
 'Our verification team needs your password before releasing {amount}.', 'Disclose the one time code to {name} to authorize your reward.',
 'Read the login digits aloud to our representative now.', 'Your refund is waiting; transmit the secret code from your SMS.',
 'Your wallet will expire unless you tell our agent the PIN.', 'To claim {amount}, reply with your verification code.',
 'Give your password to the service desk immediately.', 'Send your OTP to recover the blocked funds.',
 'The caller needs the private login token to finish the refund.', 'Unlock your payment by forwarding the authentication digits.',
 'A support officer is requesting your confidential passcode.', 'Let our agent know the six secret digits sent to your phone.'
],
'phishing': [
 'Your account is blocked. Click this link to verify identity: https://{name}-secure.example/login',
 'Wallet suspended. Verify now at https://restore-{name}.example.',
 'Last warning: update your banking login at https://{name}-check.example.',
 'Claim your prize of {amount}; pay the processing fee first.',
 'Account frozen. Click the restore link and enter your password.',
 'You won a lottery reward! Pay a deposit of {amount} to collect.',
 'Urgent: confirm your card details at https://{name}-verify.example.',
 'Unclaimed grant available. Deposit a fee to release your grant.',
 'A security issue requires signing in through https://{name}-help.example.',
 'Act now to avoid suspension. Use this wallet validation portal.',
 'Reauthenticate your banking credentials using our attached web form.',
 'Access to funds will end unless you visit the recovery portal.',
 'Congratulations on a prize of {amount}. Pay the delivery fee now.',
 'Your account is suspended; click our link to restore it.',
 'Wallet blocked. Verify with this external login page immediately.',
 'Reward notification: pay an activation fee before payout.',
 'Secure your deposits by entering credentials on this replacement website.',
 'A pending bonus requires an upfront activation payment.',
 'Follow this alternate sign in page to prevent closure of your savings.',
 'Receive the inheritance after settling the administrative charge.'
],
'impersonation': [
 'I am your bank agent {name}. Transfer {amount} to my personal wallet to restore access.',
 'This is the bank manager. Move your savings to our safe account immediately.',
 'Hello, your CEO {name} needs a confidential transfer of {amount} now.',
 'Police fraud team here. Send funds to our secure holding account.',
 'Your mobile service agent requires an emergency wallet transfer.',
 'I work for the central bank. Transfer the balance for a security audit.',
 'This is {name} from support. Pay my personal account to unfreeze your funds.',
 'Family emergency, this is my new number. Send {amount} without calling.',
 'Tax officer {name} demands immediate payment to this wallet or arrest follows.',
 'Bank security requires you to shift money to an account we control.',
 'Your director requests an off the record wire to a new beneficiary.',
 'A regulator instructs you to relocate deposits to a temporary account.',
 'I am the bank agent. Send {amount} to me urgently for verification.',
 'Company president here. Make a secret payment before the meeting.',
 'Fraud investigator calling: transfer your savings for safekeeping.',
 'This is your cousin on a new phone. Pay me and do not call back.',
 'An official auditor asks that funds be moved to their private balance.',
 'Your supervisor needs a discreet remittance outside normal approvals.',
 'A relative using an unfamiliar number requests money and refuses a call.',
 'The supposed bank employee wants your deposit placed in their own wallet.'
]}

def prepare():
    cfg=load_config(); rng=np.random.default_rng(cfg['seed']); path=Path(cfg['paths']['data']); path.mkdir(exist_ok=True)
    texts=[]
    for label, templates in TEMPLATES.items():
        for i, template in enumerate(templates):
            split='train' if i<12 else 'validation' if i<16 else 'test'
            for j in range(12 if split=='train' else 5):
                text=template.format(amount=int(rng.integers(100,10000)),name=rng.choice(['River','Amina','Union','North','Delta','Sam']))
                texts.append(dict(text=text,label=label,fraud=int(label!='legitimate'),split=split,template_id=f'{label}_{i}'))
    pd.DataFrame(texts).to_csv(path/'texts.csv',index=False)
    rows=[]; base=datetime(2026,1,1,tzinfo=timezone.utc); t=base
    # Profiles are scenario inputs, never passed as known fraud labels to the scorer.
    for i in range(3600):
        t += timedelta(seconds=int(rng.integers(30,150)))
        split='train' if i<2160 else 'validation' if i<2880 else 'test'
        mode=rng.choice(['legit','social','behavior','mule'],p=[.90,.035,.035,.03])
        fraud=int(mode!='legit'); sender=f'a{rng.integers(0,100)}'; recipient=f'p{rng.integers(0,50)}'
        amount=float(round(rng.lognormal(5.0,.65),2)); age=int(rng.integers(30,1500))
        device=f'd-{sender}'; ip=f'ip-{sender}'
        if mode=='behavior':
            amount*=float(rng.uniform(5,18)); age=int(rng.integers(1,90)); device=f'new-{i}'
        if mode=='mule':
            recipient=f'mule{rng.integers(0,3)}'; device='shared-ring'; ip='ring-ip'
            if rng.random()<.4: sender=f'mule{rng.integers(0,3)}'; recipient=f'exit{rng.integers(0,5)}'
        if mode=='legit' and rng.random()<.05: amount*=7  # legitimate anomalies
        text_label=rng.choice(['otp_scam','phishing','impersonation']) if mode=='social' else 'legitimate'
        if mode!='social' and rng.random()<.4: text=None
        else:
            options=[x['text'] for x in texts if x['split']==split and x['label']==text_label]
            text=str(rng.choice(options))
        rows.append(dict(transaction_id=f'tx-{i:05}',sender_id=sender,recipient_id=recipient,amount=round(amount,2),
                         timestamp=t.isoformat(),account_age_days=age,device_id=device,ip_address=ip,
                         relationship_group=sender,country='AA' if rng.random()>.03 else 'BB',text=text,
                         fraud=fraud,text_label=text_label,scenario=mode,split=split))
    pd.DataFrame(rows).to_csv(path/'transactions.csv',index=False)
    (path/'provenance.json').write_text(json.dumps(dict(source='Original synthetic templates and transaction scenarios; not PaySim',
        seed=cfg['seed'],rows=len(rows),text_rows=len(texts),split='60/20/20 chronological transactions; disjoint text templates',
        caveat='Same generator across splits. Metrics measure synthetic scenario recovery, not bank deployment readiness.'),indent=2))
    print(f'Prepared {len(rows)} transactions and {len(texts)} texts')
if __name__=='__main__': prepare()
