from peanalyzer.backend.insertion_products import insertion_products


def test_exclusive_whole_products_include_unresolved_native_rows():
    wt,pe='CATG','CAACTTG'
    def row(query,name='Reference',ref='CATG'):
        if len(query)>len(ref): ref=ref[:2]+'-'*(len(query)-len(ref))+ref[2:]
        return dict(Aligned_Sequence=query,Reference_Sequence=ref,Reference_Name=name,**{'#Reads':'2'})
    refs={'Reference':{'sequence':wt},'Prime-edited':{'sequence':pe}}
    obs=[row(wt),row(pe,'Prime-edited',pe),row('CAATT'),row('CACG'),row('AAACTTG','Prime-edited',pe),
         row('CAACTACTTG'),row('CAAATTGTG'),row('CAATG'),row('CAGCCTG'),
         row(wt,'AMBIGUOUS_Reference'),row('CANT'),row('-ATG')]
    result=insertion_products(wt,pe,refs,obs)
    assert result['aligned_reads']==sum(result['counts'].values())==24
    assert result['counts']=={'exact_WT':2,'exact_intended_insertion':2,'partial_intended_insert':2,
        'alternate_same_length_insert':2,'intended_insert_with_flank_substitutions':2,'tandem_intended_insert':2,
        'unexpected_longer_product':2,'other_observed_product':4,'unresolved_aligned':6}


def test_nonunique_junction_and_multiple_edit_regions_do_not_assign_insert_categories():
    assert insertion_products('AAA','AAAA',{},[]) is None
    assert insertion_products('CCG','CCAAGT',{},[]) is None
