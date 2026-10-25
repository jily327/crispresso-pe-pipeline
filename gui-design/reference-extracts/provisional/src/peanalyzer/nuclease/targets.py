"""Versioned nuclease targeting geometry; this module does not call variants."""
import re
from typing import Literal
from pydantic import field_validator, model_validator
from peanalyzer.schemas import Model, Identifier, sequence, reverse_complement


def intervals(text, length):
    if not isinstance(text,str) or not re.fullmatch(r'\d+-\d+(?:_\d+-\d+)*',text):
        raise ValueError('NUCLEASE_WINDOW_REQUIRED: nonempty zero-based inclusive ranges; sentinel 0 is not a window')
    result=[];previous=-1
    for part in text.split('_'):
        start,end=map(int,part.split('-'))
        if start>end or start<=previous or end>=length:
            raise ValueError('NUCLEASE_WINDOW_INVALID: ordered disjoint in-bounds intervals required')
        result.append([start,end]);previous=end
    return result


def coordinate_string(ranges):
    return '_'.join(f'{start}-{end}' for start,end in ranges)


def tigr_geometry(wt,target,window='W2'):
    if len(target)!=18:
        raise ValueError('TIGR_TARGET_LENGTH: target must be exactly 18 nt')
    hits={}
    for orientation,query in (('forward',target),('reverse',reverse_complement(target))):
        for start in range(len(wt)-17):
            if wt[start:start+18]==query:hits.setdefault(start,set()).add(orientation)
    if len(hits)!=1:
        raise ValueError('TIGR_TARGET_NOT_UNIQUE' if hits else 'TIGR_TARGET_MISSING')
    start,orientations=next(iter(hits.items()))
    orientation='palindromic' if len(orientations)==2 else next(iter(orientations))
    windows={'W1':[[start+4,start+5],[start+12,start+13]],'W2':[[start+4,start+13]],
             'W3':[[start,start+17]],'W4':[[max(0,start-10),min(len(wt)-1,start+27)]]}
    if window not in windows:raise ValueError('unknown TIGR window')
    return dict(derivation='tigr_tas_v1',profile_version='tigr_tas_v1',target_sequence=target,
        target_start=start,target_interval=[start,start+17],orientation=orientation,
        physical_nick_boundaries=[[start+4,start+5],[start+12,start+13]],
        target_oriented_nick_labels=None if orientation=='palindromic' else
            (['5|6','13|14'] if orientation=='forward' else ['13|14','5|6']),
        amplicon_top_strand_target=wt[start:start+18],amplicon_top_strand_between_cuts=wt[start+5:start+13],
        target_oriented_between_cuts=None if orientation=='palindromic' else
            (wt[start+5:start+13] if orientation=='forward' else reverse_complement(wt[start+5:start+13])),
        selected_window=window,intervals=windows[window],coordinates=coordinate_string(windows[window]))


class NucleaseTarget(Model):
    analysis_mode: Literal['indel_nuclease']
    target_name: Identifier
    copy_name: Identifier
    wt_sequence: str
    quantification_window_coordinates: str | None=None
    nuclease_profile: Literal['tigr_tas_v1'] | None=None
    tigr_target_sequence: str | None=None
    tigr_window: Literal['W1','W2','W3','W4'] | None=None
    insertion_quantification_mode: Literal['current']='current'

    @field_validator('target_name','copy_name')
    @classmethod
    def identifier(cls,value):
        if '__' in value:raise ValueError('double underscore is reserved')
        return value

    @field_validator('wt_sequence','tigr_target_sequence')
    @classmethod
    def dna(cls,value):return None if value is None else sequence(value)

    @model_validator(mode='after')
    def definition(self):
        if self.nuclease_profile:
            if self.tigr_target_sequence is None:raise ValueError('TIGR target required')
            if self.quantification_window_coordinates is not None:raise ValueError('choose explicit window or profile, not both')
            if self.tigr_window is None:self.tigr_window='W2'
            tigr_geometry(self.wt_sequence,self.tigr_target_sequence,self.tigr_window)
        else:
            if self.tigr_target_sequence is not None or self.tigr_window is not None:raise ValueError('TIGR fields require profile')
            self.quantification_window_coordinates=coordinate_string(intervals(self.quantification_window_coordinates,len(self.wt_sequence)))
        return self

    @property
    def amplicon_id(self):return f'{self.target_name}__{self.copy_name}'

    @property
    def window(self):
        if self.nuclease_profile:return tigr_geometry(self.wt_sequence,self.tigr_target_sequence,self.tigr_window)
        return dict(derivation='explicit',profile_version=None,coordinates=self.quantification_window_coordinates,
                    intervals=intervals(self.quantification_window_coordinates,len(self.wt_sequence)))

    @property
    def scientific_identity(self):
        return dict(**self.model_dump(mode='json'),resolved_window=self.window,
            backend_settings=dict(exclude_bp_from_left=0,exclude_bp_from_right=0,
                ignore_substitutions=False,ignore_insertions=False,ignore_deletions=False,
                use_legacy_insertion_quantification=False,write_detailed_allele_table=True))
