import os

import torch
import stanfordcorenlp
import torch.utils.data
from nltk.tokenize import word_tokenize
from sklearn import preprocessing
import numpy as np
from collections import Counter
import pickle

from ..data.data import GraphData
from ..modules.utils.vocab_utils import VocabModel, Vocab

from ..modules.utils.tree_utils import Vocab as VocabForTree
from ..modules.utils.tree_utils import Tree

import json
from ..data.dataset import SequenceLabelingDataset
from dependency_graph_construction_without_tokenize import DependencyBasedGraphConstruction_without_tokenizer
dataset_root = '../test/dataset/conll/'
from graph4nlp.pytorch.modules.graph_construction.ie_graph_construction import IEBasedGraphConstruction
from graph4nlp.pytorch.modules.graph_construction.constituency_graph_construction import ConstituencyBasedGraphConstruction
from line_graph_construction import LineBasedGraphConstruction


class ConllDataset(SequenceLabelingDataset):
    @property
    def raw_file_names(self):
        """3 reserved keys: 'train', 'val' (optional), 'test'. Represent the split of dataset."""        
        return {'train':'eng.train','test':'eng.testa','val':'eng.testb'}

    @property
    def processed_file_names(self):
        """At least 3 reserved keys should be fiiled: 'vocab', 'data' and 'split_ids'."""
        return {'vocab': 'vocab.pt', 'data': 'data.pt', 'split_ids': 'split_ids.pt'}

    #def download(self):
    #    raise NotImplementedError(
    #        'This dataset is now under test and cannot be downloaded. Please prepare the raw data yourself.')

    def __init__(self, root_dir, topology_builder=None, topology_subdir=None, graph_type='static',
                 edge_strategy=None, merge_strategy=None,tag_types=None, dynamic_init_graph_type=None, dynamic_init_topology_builder=None, **kwargs):
        super(ConllDataset, self).__init__(root_dir=root_dir, topology_builder=topology_builder,
                                          topology_subdir=topology_subdir, graph_type=graph_type,
                                          edge_strategy=edge_strategy, merge_strategy=merge_strategy,tag_types=tag_types, dynamic_init_topology_builder=dynamic_init_topology_builder, **kwargs)
        self.dynamic_init_topology_aux_args={'lower_case': self.lower_case,
                            'tokenizer': self.tokenizer,
                            'merge_strategy': self.merge_strategy,
                            'edge_strategy': self.edge_strategy,
                            'verbase': False}
        self.dynamic_init_topology_builder=dynamic_init_topology_builder

        
    def build_topology(self, data_items):
        """
        Build graph topology for each item in the dataset. The generated graph is bound to the `graph` attribute of the
        DataItem.
        """
        print('Connecting to stanfordcorenlp server...')
        processor = stanfordcorenlp.StanfordCoreNLP('F:/xiaojie/stanford-corenlp-4.1.0', port=9000+np.random.randint(50), timeout=100)
        print('CoreNLP server connected.')
        if self.graph_type == 'static':                        
            if self.topology_builder == IEBasedGraphConstruction:
                props_coref = {
                    'annotators': 'tokenize, ssplit, pos, lemma, ner, parse, coref',
                    "tokenize.options":
                        "splitHyphenated=true,normalizeParentheses=true,normalizeOtherBrackets=true",
                    "tokenize.whitespace": False,
                    'ssplit.isOneSentence': False,
                    'outputFormat': 'json'
                }
                props_openie = {
                    'annotators': 'tokenize, ssplit, pos, ner, parse, openie',
                    "tokenize.options":
                        "splitHyphenated=true,normalizeParentheses=true,normalizeOtherBrackets=true",
                    "tokenize.whitespace": False,
                    'ssplit.isOneSentence': False,
                    'outputFormat': 'json',
                    "openie.triple.strict": "true"
                }
                processor_args = [props_coref, props_openie]
            elif self.topology_builder == DependencyBasedGraphConstruction_without_tokenizer:
                processor_args = {
                    'annotators': 'ssplit,tokenize,depparse',
                    "tokenize.options":
                        "splitHyphenated=false,normalizeParentheses=false,normalizeOtherBrackets=false",
                    "tokenize.whitespace": False,
                    'ssplit.isOneSentence': False,
                    'outputFormat': 'json'
                }
            elif self.topology_builder == LineBasedGraphConstruction:
                processor_args = {
                    'annotators': 'ssplit,tokenize,depparse',
                    "tokenize.options":
                        "splitHyphenated=false,normalizeParentheses=false,normalizeOtherBrackets=false",
                    "tokenize.whitespace": False,
                    'ssplit.isOneSentence': False,
                    'outputFormat': 'json'
                }                    
            elif self.topology_builder == ConstituencyBasedGraphConstruction:
                processor_args = {
                    'annotators': "tokenize,ssplit,pos,parse",
                    "tokenize.options":
                    "splitHyphenated=true,normalizeParentheses=true,normalizeOtherBrackets=true",
                    "tokenize.whitespace": False,
                    'ssplit.isOneSentence': False,
                    'outputFormat': 'json'
                }
            else:
                raise NotImplementedError
            
            for item in data_items:
                graph = self.topology_builder.topology(raw_text_data=item.input_text,
                                                       nlp_processor=processor,
                                                       processor_args=processor_args,
                                                       merge_strategy=self.merge_strategy,
                                                       edge_strategy=self.edge_strategy,
                                                       verbase=False,auxiliary_args=None)
                item.graph = graph
        elif self.graph_type == 'dynamic':
            if self.dynamic_graph_type == 'node_emb':
                for item in data_items:
                    graph = self.topology_builder.init_topology(item.input_text,
                                                                lower_case=self.lower_case,
                                                                tokenizer=self.tokenizer)
                    item.graph = graph
            elif self.dynamic_graph_type == 'node_emb_refined':
                if self.init_topology_builder in (IEBasedGraphConstruction, ConstituencyBasedGraphConstruction):
                    print('Connecting to stanfordcorenlp server...')
                    processor = self.processor
                    
                    if self.init_topology_builder == IEBasedGraphConstruction:
                        props_coref = {
                            'annotators': 'tokenize, ssplit, pos, lemma, ner, parse, coref',
                            "tokenize.options":
                                "splitHyphenated=true,normalizeParentheses=true,normalizeOtherBrackets=true",
                            "tokenize.whitespace": False,
                            'ssplit.isOneSentence': False,
                            'outputFormat': 'json'
                        }
                        props_openie = {
                            'annotators': 'tokenize, ssplit, pos, ner, parse, openie',
                            "tokenize.options":
                                "splitHyphenated=true,normalizeParentheses=true,normalizeOtherBrackets=true",
                            "tokenize.whitespace": False,
                            'ssplit.isOneSentence': False,
                            'outputFormat': 'json',
                            "openie.triple.strict": "true"
                        }
                        processor_args = [props_coref, props_openie]
                    elif self.init_topology_builder == DependencyBasedGraphConstruction_without_tokenizer:
                        processor_args = {
                            'annotators': 'ssplit,tokenize,depparse',
                            "tokenize.options":
                                "splitHyphenated=false,normalizeParentheses=false,normalizeOtherBrackets=false",
                            "tokenize.whitespace": False,
                            'ssplit.isOneSentence': False,
                            'outputFormat': 'json'
                        }
                    elif self.init_topology_builder == ConstituencyBasedGraphConstruction:
                        processor_args = {
                            'annotators': "tokenize,ssplit,pos,parse",
                            "tokenize.options":
                            "splitHyphenated=true,normalizeParentheses=true,normalizeOtherBrackets=true",
                            "tokenize.whitespace": False,
                            'ssplit.isOneSentence': False,
                            'outputFormat': 'json'
                        }
                    else:
                        raise NotImplementedError
                    print('CoreNLP server connected.')
                else:
                    processor = None
                    processor_args = None

                for item in data_items:
                    graph = self.topology_builder.init_topology(item.input_text,
                                                                dynamic_init_topology_builder=self.dynamic_init_topology_builder,
                                                                dynamic_init_topology_aux_args=self.dynamic_init_topology_aux_args)

                    item.graph = graph
            else:
                raise RuntimeError('Unknown dynamic_graph_type: {}'.format(self.dynamic_graph_type))

        else:
            raise NotImplementedError('Currently only static and dynamic are supported!')

if __name__ == '__main__':
    ConllDataset(root_dir='../test/dataset/conll/', topology_builder=DependencyBasedGraphConstruction,
                topology_subdir='DependencyGraph',tag_types=['I-MISC', 'O', 'B-MISC', 'I-LOC', 'I-PER', 'I-ORG'])
