#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# %% INSTALL
import os, shutil, itertools, json, time #GENERIC UTILS

#STAT LIBS
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.pyplot import cm

import numpy as np

from outliers import smirnov_grubbs as grubbs

import pandas as pd

import pingouin as pg

import pprint

import scipy
from scipy.stats import pearsonr
import scipy.stats as stats
from scipy.stats import ttest_ind

import seaborn as sns

from sklearn.preprocessing import StandardScaler # mean = 0 vairance =1
from sklearn.decomposition import PCA

from statannotations.Annotator import Annotator
from statannot import add_stat_annotation

from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.multicomp import MultiComparison

# import weasyprint


######## CONSTANTS ######################
# Constants are like variables that should not be rewritten, they are declared in all caps by convention
ROOT = os.getcwd() #This gives terminal location (terminal working dir)
INPUT_DIR = f'{ROOT}/input'
OUTPUT_DIR = f'{ROOT}/output'
CACHE_DIR = f'{INPUT_DIR}/cache'


########## UTILITARIES ############
#Check filesystem is set up for write operations
def setTreatment(filename, treatment_mapping):
    subcache_dir = f"{CACHE_DIR}/{filename.split('.')[0]}"
    checkFilesystem(subcache_dir)
    saveJSON(f"{subcache_dir}/treatment_mapping.json", treatment_mapping)
    print(f"TREATMENT MAPPING {treatment_mapping} SAVED TO {subcache_dir} SUBCACHE")

#This function saves dictionnaries, JSON is a dictionnary text format that you use to not have to reintroduce dictionnaries as variables 
def saveJSON(path, dict_to_save):
    print(dict_to_save, path)
    with open(path, 'w', encoding ='utf8') as json_file:
        json.dump(dict_to_save, json_file)
    print(f"TREATMENT DICT SAVED TOO {path}") 
            
#This function gets JSON files and makes them into python dictionnaries
def getJSON(path):
    with open(path) as outfile:
        treatment_mapping = json.load(outfile)
    return treatment_mapping

#This checks that the filesystem has all the requisite folders (input, cache, etc..) and creates them if not
def checkFilesystem(file_path=None):
    if not os.path.exists(INPUT_DIR):
        os.mkdir(INPUT_DIR)
        print('CREATED INPUT DIRECTORY, ADD .csv FILE TO START')
        if not os.path.exists(CACHE_DIR):
            os.mkdir(CACHE_DIR)
    if not os.path.exists(OUTPUT_DIR):
        os.mkdir(OUTPUT_DIR)
    if file_path and not os.path.exists(file_path):
        os.mkdir(file_path)

#This function deletes all cached files, it is used when you want to start from square one because all intermediary results will be cached
def resetCache():
    shutil.rmtree(CACHE_DIR)
    os.mkdir(CACHE_DIR)
    print('CACHE CLEARED')

#This function cahces (aka saves in a easily readable format) all dataframes used
def cacheDf(filename, df_type, df):
    cache_subdir = f'{CACHE_DIR}/{filename}'
    if not os.path.exists(cache_subdir):
        os.mkdir(cache_subdir)
    df.to_pickle(f'{cache_subdir}/{df_type}.pkl')
    print(f'CREATED {cache_subdir}/{df_type}.pkl CACHE')

#This function gets the dataframes that are cached
def getCache(filename, df_type):
    print(f'GETTING "{df_type}" FROM "{filename}" CACHE')
    return pd.read_pickle(f'{CACHE_DIR}/{filename}/{df_type}.pkl')

#This checks if a particulat dataframe/dataset is cached, return boolean
def isCached(filename, df_type):
    return os.path.isfile(f'{CACHE_DIR}/{filename}/{df_type}.pkl')

def applyTreatmentMapping(df, mapping):
    df['group_no'] = df.apply(lambda x: mapping[str(int(x['group_no']))], axis=1)
    return df.rename(columns={'group_no': 'treatment'})
    

########### GETTERS #################    

#Generic df getter
#First checks cache to see if the df already has been built and saved in cache
#If not it uses the builder callback to build the df appropriately
def getOrBuildDf(filename, df_type, builder_cb):
    filename_no_extension = filename.split(".")[0]
    if isCached(filename_no_extension, df_type): #Check cache to avoid recalcuating from scratch if alreasy done
        return getCache(filename_no_extension, df_type)
    print(f'BUILDING "{df_type}"')    #Build useing callback otherwise and cache result
    df = builder_cb(filename)
    cacheDf(filename_no_extension, df_type, df)
    return df

#The three getters that follow just used the generic function to get the df if cached, injecting their own specific functions to build the df in the case where its not chached
def getRawDf(filename):
    return getOrBuildDf(filename, 'raw_df', buildRawDf)

def getRestructuredDf(filename):
    return getOrBuildDf(filename, 'restructured_df', buildRestructureDf)

def getRatiosDf(filename, treatment_mapping=None):
    if treatment_mapping:
        subcache_dir = f"{CACHE_DIR}/{filename.split('.')[0]}"
        checkFilesystem(subcache_dir)
        saveJSON(f"{subcache_dir}/treatment_mapping.json", treatment_mapping)
    return getOrBuildDf(filename, 'ratios_df', buildRatiosDf)

#Generic function to select any ratio imaginable and return the corresponding df
def selectRatio(region_1, region2, compound_1, compound2, ratios_df):
    return ratios_df.loc[(ratios_df['BR_1']==region_1) & (ratios_df['compound_1']==compound_1) & (ratios_df['BR_2']==region_2) & (ratios_df['compound_2']==compound_2)]

#Function to get the specific rations (intra region) that you use based on a ratios dictionnary
def getRatiosPerRegion(ratios_df, ratios_mapping):
    ratios_df = ratios_df[ratios_df.BR_1==ratios_df.BR_2]
    compound_ratios = []
    for compound_1, compound_2_list in ratios_mapping.items():
        for compound_2 in compound_2_list:
            compound_ratios.append(ratios_df[(ratios_df['compound_1']==compound_1) & (ratios_df['compound_2']==compound_2)])
    return pd.concat(compound_ratios)


############ BUILDERS #########

#Contains the logic to build the raw df from the csv file
def buildRawDf(filename):
    file_name, file_type = filename.split('.')
    if not file_type == 'csv':
        raise Exception(f'METHOD TO DEAL WITH FILE TYPE "{file_type}" ABSENT')
    if not os.path.isfile(f'{INPUT_DIR}/{filename}'):
        raise Exception(f'FILE {filename} IS ABSENT IN "input/" DIRECTORY')
    raw_df = pd.read_csv(f'{INPUT_DIR}/{filename}', header=0).replace(np.nan, 0) # to set all 0 to Nan
    treatment_mapping = getJSON((f"{CACHE_DIR}/{file_name}/treatment_mapping.json"))
    return applyTreatmentMapping(raw_df, treatment_mapping)

#contains the logic to build the df in the new format based on raw df
def buildRestructureDf(filename):
    raw_df = getRawDf(filename)
    col_names = ['mouse_id' , 'treatment' , 'BR' , 'compound' , 'ng_mg']
    

    raw_col_names = raw_df.columns.copy()
    result_rows = []

    for ind, row in raw_df.iterrows(): #loop for row get mouse and group
        
        mouse_id = row[0]
        treatment = row[1]

        for val, col_name in zip(row[2:], raw_col_names[2:]): #loop within row

            if val > 0:
                compound, BR = col_name.split('_')
                result_rows.append([mouse_id, treatment, BR, compound, val])
    
    restructured_df = pd.DataFrame(result_rows, columns=col_names)
    return pd.DataFrame(result_rows, columns=col_names)
    
#Contains the logic to build the ratios df based on the df with the new format
def buildRatiosDf(filename):
    restructured_df = getRestructuredDf(filename) #.iloc[0:100] #To speed up testing
    merged = pd.merge(left=restructured_df, right=restructured_df, on='mouse_id', suffixes=['_1', '_2']) #merge every BR/compound combo to every other for each mouse
    merged = merged[~(merged.BR_1 == merged.BR_2) & ~(merged.compound_1 == merged.compound_2)] #eliminate duplicates ((BR1 == BR2 & C1 == C2)
    # merged = merged[(merged.BR_1 < merged.BR_2) | (merged.compound_1 < merged.compound_2) #eliminate duplicates ((BR1 == BR2 & C1 == C2) and cross combinations (row1: BR1=A, C1=B, BR2=C, C2=D; row2: BR1=C, C1=D, BR2=A, C2=B))
    #         & ~((merged.BR_1 > merged.BR_2) & (merged.compound_1 < merged.compound_2))] #Uncomment code to only save half the ration (C1/C2) to divide time it takes by 2
    merged[['compounds', 'ratio']] = merged.apply(lambda x: [f'{x.compound_1}/{x.compound_2}', x.ng_mg_1 / x.ng_mg_2], axis=1, result_type='expand') #calculate the ratio
    return merged.rename(columns={'treatment_1': 'treatment'}).drop(columns=['treatment_2', 'ng_mg_1', 'ng_mg_2']) #Drop duplicate columns
    

############### CALCULATE/STATISTICS ############

def plotAnything(anything):
    return plt(anything)

def showOutliers(raw_df):
    return plotAnything(getOutliers(raw_df))

def getOutliers(raw_df):
    return [doRawDfGrubbs(raw_df), doRawDfGrubbs(raw_df)]
    

def doRawDfGrubbs(raw_df):
    result_list = []
    for group in raw_df.groupby('treatment'):
        result_list.append(grubbsTest(raw_df)) #this func will loop through the df to feel grubbsTest
    return result_list
    
    

def grubbsTest(group_list): #include the vairable type in name i.e. group_list series
    return


######## INIT ##########
#Start by checking filesystem has all the folders necessary for read/write operations (cache) or create them otherwise
checkFilesystem()