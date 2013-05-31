'''
Created on Apr 7, 2013

@author: agross
'''
from Processing.Helpers import get_vec_type, to_quants
from Processing.Tests import get_cox_ph_ms

import pandas as pd
import matplotlib.pylab as plt
import pandas.rpy.common as com
import rpy2.robjects as robjects 

import numpy as np

survival = robjects.packages.importr('survival')
base = robjects.packages.importr('base')

def get_markers(censoring, survival):
    '''
    Get locations for markers in KM plot.
    censoring is a list of censoring times.
    survival is a time-series of survival values
    '''
    markers = []
    for cc in censoring:
        d = (pd.Series(survival.index, survival.index, dtype=float) - cc)
        t = d[d<=0].idxmax()
        markers += [(cc, survival[t])]
    return markers

def draw_survival_curves_mpl(fit, ax=None, title=None, colors=None):
    '''
    Takes an R survfit.
    '''
    if ax is None:
        _, ax = plt.subplots(1,1, figsize=(4,3))
    s = base.summary(fit)
    tab = pd.DataFrame({v: s.rx2(v) for v in s.names 
                                    if len(s.rx2(v)) == len(s.rx2('time'))}, 
                       index=s.rx2('time'))
    call = com.convert_robj(fit.rx2('call')[2])
    
    #groups = sorted(call.feature.unique(), key=lambda s: sum(call.feature==s))
    groups = call.feature.value_counts().index
    groups = robjects.r.sort(robjects.r.c(*call.feature.unique()))
    groups = np.roll(groups, len(tab.strata.unique()))
    
    if len(tab.strata.unique()) == 1: #TODO: fix for more than one curve
        groups = call.feature.value_counts().index
    if len(tab.strata.unique()) != len(groups):
        tab.strata = tab.strata - (len(tab.strata.unique()) - len(groups))
           
    for i,group in enumerate(groups):
        censoring = call[(call.event==0) * (call.feature==group)].days
        surv = tab[tab.strata==(i+1)].surv
        surv = surv.set_value(0., 1.).sort_index()  #Pandas bug, needs to be float
        if surv.index[-1] < censoring.max():
            surv = surv.set_value(censoring.max(), surv.iget(-1)).sort_index()

        censoring_pos = get_markers(censoring, surv)
        ax.step(surv.index, surv, lw=3, where='post', alpha=.7, label=group)
        if colors is not None:
            ax.lines[-1].set_color(colors[i])
        if len(censoring_pos) > 0:
            ax.scatter(*zip(*censoring_pos), marker='|', s=80, 
                       color=ax.lines[-1].get_color())
        
    ax.set_ylim(0,1.05)
    #ax.set_xlim(0, max(surv.index)*1.05)
    ax.set_xlim(0, max(call.days)*1.05)
    ax.legend(loc='best')
    ax.set_ylabel('Survival')
    ax.set_xlabel('Years')
    if title:
        ax.set_title(title)
        
def process_feature(feature, q, std):
    if (get_vec_type(feature) == 'real') and (len(feature.unique()) > 10):
        feature = to_quants(feature, q=q, std=std, labels=True)
    return feature

def draw_survival_curve(feature, surv, q=.25, std=None, **args):
    feature = process_feature(feature, q, std)
    fmla = robjects.Formula('Surv(days, event) ~ feature')           
    m = get_cox_ph_ms(surv, feature, return_val='model', formula=fmla)
    r_data = m.rx2('call')[2]
    #s = survival.survdiff(fmla, r_data)
    #p = str(s).split('\n\n')[-1].strip().split(', ')[-1]
    draw_survival_curves_mpl(survival.survfit(fmla, r_data), **args)
    
def draw_survival_curves(feature, surv, assignment=None):
    if assignment is None:
        draw_survival_curve(feature, surv)
        return
    num_plots = len(assignment.unique())
    fig, axs = plt.subplots(1,num_plots, figsize=(num_plots*4,3), sharey=True)
    for i,(l,s) in enumerate(feature.groupby(assignment)):
        draw_survival_curve(s, surv, ax=axs[i], 
                            title='{} = {}'.format(assignment.name,l))
        
def survival_stat_plot(t, axs=None):
    if axs is None:
        fig = plt.figure(figsize=(6,1.5))
        ax = plt.subplot2grid((1,3), (0,0), colspan=2)
        ax2 = plt.subplot2grid((1,3), (0,2))
    else:
        ax, ax2 = axs
        fig = plt.gcf()
    for i,(idx,v) in enumerate(t.iterrows()):
        conf_int = v['Median Survival']
        median_surv = v[('Median Survival','Median')]
        if (v['Stats']['# Events']  / v['Stats']['# Patients']) < .5:
            median_surv = np.nanmin([median_surv, 6])
            conf_int['Upper'] = np.nanmin([conf_int['Upper'], 6])
        l = ax.plot(*zip(*[[conf_int['Lower'],i], [median_surv,i], [conf_int['Upper'],i]]), lw=3, ls='--', 
                    marker='o', dash_joinstyle='bevel')
        ax.scatter(median_surv,i, marker='s', s=100, color=l[0].get_color(), edgecolors=['black'], zorder=10,
                   label=idx)
    ax.set_yticks(range(len(t)))
    ax.set_yticklabels(['{} ({})'.format(idx, int(t.ix[idx]['Stats']['# Patients'])) 
                        for idx in t.index])
    ax.set_ylim(-.5, i+.5)
    ax.set_xlim(0,5)
    ax.set_xlabel('Median Survival (Years)')
    
    tt = t['5y Survival']
    b = (tt['Surv']).plot(kind='barh', ax=ax2, 
         color=[l.get_color() for l in ax.lines],
         xerr=[tt.Surv-tt.Lower, tt.Upper-tt.Surv], ecolor='black')
    ax2.set_xlabel('5Y Survival')
    ax2.set_xticks([0, .5, 1.])
    ax2.set_yticks([])
    fig.tight_layout()
    
def plot_5y(t, ax):
    tt = t['5y Survival']
    b = ax.bar(range(len(tt)), tt['Surv'],
         color=plt.rcParams['axes.color_cycle'],
         yerr=[tt.Surv-tt.Lower, tt.Upper-tt.Surv], ecolor='black')
    ax.yaxis.set_ticks_position('left')
    ax.xaxis.set_ticks_position('bottom')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_position(('data', 0))
    #adjust_spines(ax,['left','bottom'])
    ax.spines['left'].set_position(('data', 0))
    
    ax.set_xticks(np.arange(len(tt))+.4)
    ax.set_xticklabels(['n={}'.format(int(t.ix[idx]['Stats']['# Patients']))
                        for idx in t.index], rotation=0)
    
    ax.set_ylabel('5Y Survival', position=(0.5,.66))
    ax.set_yticks([0, .5, 1.])
    #ax.yaxis.set_data_interval(0,1)
    ax.spines['left'].set_bounds(0, 1)
    ax.spines['bottom'].set_bounds(0, len(tt))
    
    for i,idx in enumerate(t.index):
        ax.annotate(idx[1], (i + .4, -.2), ha='center')
    
    ax.hlines(-.25, 0, 1.9)  
    ax.annotate(t.index.names[0], (1, -.35), ha='center')
    ax.annotate(t.index.names[1], (0, -.2), ha='right')
    ax.set_ylim(-.5,1)
    ax.set_xlim(-1,len(tt))
    ax.set_xlim(-2.,len(tt))
    
def plot_5y2(t, ax):
    tt = t['5y Survival']
    b = ax.bar(range(len(tt)), tt['Surv'],
         color=plt.rcParams['axes.color_cycle'][1],
         yerr=[tt.Surv-tt.Lower, tt.Upper-tt.Surv], ecolor='black')
    ax.yaxis.set_ticks_position('left')
    ax.xaxis.set_ticks_position('bottom')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_position(('data', 0))
    #adjust_spines(ax,['left','bottom'])
    ax.spines['left'].set_position(('data', 0))
    
    ax.set_xticks(np.arange(len(tt))+.4)
    ax.set_xticklabels([])
    #ax.set_xticklabels(['{}'.format(int(t.ix[idx]['Stats']['# Patients']))
    #                    for idx in t.index], rotation=0)
    
    ax.set_ylabel('5Y Survival', position=(0.5,.66))
    ax.set_yticks([0, .5, 1.])
    #ax.yaxis.set_data_interval(0,1)
    ax.spines['left'].set_bounds(0, 1)
    ax.spines['bottom'].set_bounds(0, len(tt))
    
    for i,idx in enumerate(t.index):
        ax.annotate(str(int(t.ix[idx]['Stats']['# Patients'])), (i + .4, -.45), 
                    ha='center')
        ax.annotate({'Mut': 'X', 'WT': ''}[idx[1]], (i + .4, -.15), ha='center')
        ax.annotate({1: 'X', 0: ''}[idx[0]], (i + .4, -.3), ha='center')
    
    #ax.hlines(-.3, 0, 1.9)  
    ax.annotate('n= ', (0, -.45), ha='right')
    ax.annotate(t.index.names[0], (0, -.3), ha='right')
    ax.annotate(t.index.names[1], (0, -.15), ha='right')
    ax.set_ylim(-.5,1)
    ax.set_xlim(-2.5,len(tt))