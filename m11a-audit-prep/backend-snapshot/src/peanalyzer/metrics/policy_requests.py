"""Prevalidate optional requests without making canonical analysis depend on them."""
from collections import Counter
from dataclasses import dataclass
import math

from pydantic import ValidationError
from peanalyzer.metrics.family_models import FamilyPolicy


def json_value(value, depth=0):
    """Retain malformed JSON-like requests in serializable diagnostic evidence."""
    if depth>12:return {'invalid_value_type':type(value).__name__}
    if value is None or type(value) in (str,int,bool):return value
    if type(value) is float:return value if math.isfinite(value) else str(value)
    if type(value) in (list,tuple):return [json_value(v,depth+1) for v in value]
    if type(value) is dict:
        return {str(k):json_value(v,depth+1) for k,v in value.items()}
    return {'invalid_value_type':type(value).__name__}


@dataclass(frozen=True)
class PolicyRequest:
    storage_key: str
    policy_id: str
    raw: dict
    policy: FamilyPolicy | None
    reasons: tuple[str,...]


@dataclass(frozen=True)
class PolicyRequests:
    requests: tuple[PolicyRequest,...]

    def __bool__(self):return bool(self.requests)


def prepare_policies(policies, targets):
    """Validate once before canonical work; every request retains a local result.

    Missing IDs are invalid. All requests sharing a nonempty string ID are
    invalid, including the first. Internal keys for invalid requests are based
    on input order and cannot collide with any supplied user ID.
    """
    if isinstance(policies,PolicyRequests):return policies
    if policies is None:items=[]
    elif isinstance(policies,(dict,FamilyPolicy,str,bytes,int,float,bool)):items=[policies]
    else:
        try:items=list(policies)
        except (TypeError,ValueError):items=[policies]
    raw=[p.model_dump() if isinstance(p,FamilyPolicy) else p for p in items]
    ids=Counter(p['policy_id'] for p in raw if isinstance(p,dict)
                and isinstance(p.get('policy_id'),str) and p['policy_id'])
    used=set(ids);requests=[]
    anchor_length=len(sorted(targets,key=lambda t:t.copy_name)[0].wt_sequence) if targets else 0
    for index,value in enumerate(raw):
        reasons=[];policy=None
        user_id=value.get('policy_id') if isinstance(value,dict) else None
        identity=user_id if isinstance(user_id,str) else 'invalid'
        if not isinstance(value,dict):reasons.append('INVALID_TOLERANCE_POLICY')
        elif 'policy_id' not in value:reasons.append('MISSING_POLICY_ID')
        elif not isinstance(user_id,str) or not user_id:reasons.append('INVALID_POLICY_ID')
        if isinstance(user_id,str) and ids[user_id]>1:reasons.append('DUPLICATE_POLICY_ID')
        if not reasons:
            try:
                policy=FamilyPolicy.model_validate(value)
                if (policy.allowed_extra_substitution_positions is not None and
                        any(p>=anchor_length for p in policy.allowed_extra_substitution_positions)):
                    raise ValueError('position outside anchor WT')
            except (ValidationError,ValueError,TypeError):
                reasons.append('UNSUPPORTED_TOLERANCE_POLICY');policy=None
        storage_key=identity
        if reasons:
            storage_key=f'__invalid_policy_request_{index}'
            while storage_key in used:storage_key='_'+storage_key
        used.add(storage_key)
        retained=json_value(value)
        diagnostic=retained if isinstance(value,dict) else {'invalid_policy':retained}
        requests.append(PolicyRequest(storage_key,identity,diagnostic,policy,tuple(reasons)))
    return PolicyRequests(tuple(requests))
