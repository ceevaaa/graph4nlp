from graph4nlp.pytorch.data.data import from_batch, GraphData
from graph4nlp.pytorch.modules.graph_construction.dependency_graph_construction import DependencyBasedGraphConstruction
from graph4nlp.pytorch.modules.graph_embedding.gat import GAT
from graph4nlp.pytorch.modules.graph_embedding.ggnn import GGNN
from graph4nlp.pytorch.modules.graph_embedding.graphsage import GraphSAGE
from graph4nlp.pytorch.modules.prediction.generation.StdRNNDecoder import StdRNNDecoder
from graph4nlp.pytorch.modules.graph_construction.embedding_construction import WordEmbedding, RNNEmbedding
import torch
import torch.nn as nn
import torch.nn.functional as F
from .loss import Graph2seqLoss
import onmt


class Graph2seq(nn.Module):
    def __init__(self, vocab, gnn, device, word_emb_size=300, rnn_dropout=0.2, word_dropout=0.2, hidden_size=300,
                 direction_option='undirected'):
        super(Graph2seq, self).__init__()

        self.vocab = vocab
        # embedding_style = {'single_token_item': True,
        #                    'emb_strategy': "w2v_bilstm",
        #                    'num_rnn_layers': 1}

        # self.graph_topology = DependencyBasedGraphConstruction(embedding_style=embedding_style,
        #                                                        vocab=vocab.in_word_vocab,
        #                                                        hidden_size=hidden_size,
        #                                                        rnn_dropout=rnn_dropout, word_dropout=word_dropout,
        #                                                        device=device,
        #                                                        fix_word_emb=False)
        # if gnn == "GAT":
        #     self.gnn_encoder = GAT(3, hidden_size, hidden_size, hidden_size, [2, 2, 1], direction_option=direction_option,
        #                            feat_drop=0.2, attn_drop=0.2, activation=F.relu, residual=True)
        # elif gnn == "GGNN":
        #     self.gnn_encoder = GGNN(3, hidden_size, hidden_size, direction_option=direction_option, dropout=0.2)
        # elif gnn == "Graphsage":
        #     self.gnn_encoder = GraphSAGE(4, hidden_size, hidden_size, hidden_size, aggregator_type="lstm",
        #                                  direction_option=direction_option, feat_drop=0.4)
        # else:
        #     raise NotImplementedError("Please define your graph embedding method: {}".format(gnn))

        # if 'w2v' in self.graph_topology.embedding_layer.word_emb_layers:
        #     self.word_emb = self.graph_topology.embedding_layer.word_emb_layers['w2v'].word_emb_layer
        # else:
        # self.word_emb = WordEmbedding(
        #                 self.vocab.in_word_vocab.embeddings.shape[0],
        #                 self.vocab.in_word_vocab.embeddings.shape[1],
        #                 pretrained_word_emb=self.vocab.in_word_vocab.embeddings,
        #                 fix_emb=False,
        #                 device=device).word_emb_layer

        self.embeddings = onmt.modules.Embeddings(word_emb_size, self.vocab.in_word_vocab.embeddings.shape[0],
                                             word_padding_idx=vocab.in_word_vocab.PAD)

        self.seq_encoder = onmt.encoders.RNNEncoder(hidden_size=hidden_size, num_layers=1,
                                   rnn_type="LSTM", bidirectional=True,
                                   embeddings=self.embeddings)

        # self.seq_encoder = RNNEmbedding(word_emb_size,
        #                                 hidden_size,
        #                                 bidirectional=True,
        #                                 num_layers=2,
        #                                 device=device)

        self.seq_decoder = StdRNNDecoder(max_decoder_step=100,
                                         decoder_input_size=2*hidden_size if direction_option == 'bi_sep' else hidden_size,
                                         decoder_hidden_size=hidden_size, graph_pooling_strategy=None,
                                         word_emb=self.embeddings.word_lut, vocab=self.vocab.out_word_vocab,
                                         attention_type="uniform", fuse_strategy="concatenate",
                                         rnn_emb_input_size=hidden_size, use_coverage=False,
                                         tgt_emb_as_output_layer=False,
                                         dropout=0.3)

        # self.seq_decoder = onmt.decoders.decoder.StdRNNDecoder(
        #     hidden_size=hidden_size, num_layers=1, bidirectional_encoder=True,
        #     rnn_type="LSTM", embeddings=self.embeddings)

        self.loss_calc = Graph2seqLoss(self.vocab.in_word_vocab)
        # self.out_project = nn.Linear(hidden_size, self.vocab.in_word_vocab.embeddings.shape[0], bias=False)
        self.device = device

    # def forward(self, graph_list, tgt=None, require_loss=True):
    def forward(self, src_seq, src_len, tgt_seq=None, require_loss=True):
        # batch_graph = self.graph_topology(graph_list)

        # run GNN
        # batch_graph: GraphData = self.gnn_encoder(batch_graph)
        # batch_graph.node_features["rnn_emb"] = batch_graph.node_features['node_feat']
        # batch_graph.node_features["node_emb"] = batch_graph.node_features['node_feat']

        src_seq = src_seq.transpose(0, 1)
        # tgt_seq = tgt_seq.transpose(0, 1)
        enc_state, memory_bank, lengths = self.seq_encoder(src_seq.unsqueeze(-1), src_len)

        # down-task
        max_len = max(src_len)
        enc_mask = torch.arange(max_len).expand(len(src_len), max_len) < src_len.cpu().unsqueeze(1)
        enc_mask = (enc_mask.long()-1).to(self.device)
        prob, enc_attn_weights, coverage_vectors = self.seq_decoder._run_forward_pass(memory_bank.transpose(0, 1),
                                                                                      graph_node_mask=enc_mask,
                                                                                      graph_level_embedding=torch.cat((enc_state[0][0], enc_state[0][1]), dim=1),
                                                                                      tgt_seq=tgt_seq)
        # loss = self.loss_calc(prob, tgt_seq.transpose(0, 1).squeeze())

        # prob, enc_attn_weights, coverage_vectors = self.seq_decoder(from_batch(batch_graph), tgt_seq=tgt)
        if require_loss:
            loss = self.loss_calc(prob, tgt_seq.squeeze())
            return prob, loss
        else:
            return prob
