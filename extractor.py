import spacy
import networkx as nx
import math
import operator

class Extractor:

    def extract(self, text, POS_KEPT):
        nlp = spacy.load("en_core_web_sm")
        nlp.max_length = 12838008 # or even higher depends on text size
        doc = nlp(text)

        lemma_graph = nx.Graph()
        seen_lemma = {}

        for sent in doc.sents:
            self.link_sentence(doc, sent, lemma_graph, seen_lemma,POS_KEPT)


        labels = {}
        keys = list(seen_lemma.keys())

        for i in range(len(seen_lemma)):
            labels[i] = keys[i][0].lower()

        ranks = nx.pagerank(lemma_graph)

        phrases = {}
        counts = {}

        for chunk in doc.noun_chunks:
            self.collect_phrases(doc,seen_lemma, ranks, chunk, phrases, counts)

        min_phrases = {}

        for compound_key, rank_tuples in phrases.items():
            l = list(rank_tuples)
            l.sort(key=operator.itemgetter(1), reverse=True)
            
            phrase, rank = l[0]
            count = counts[compound_key]
            
            min_phrases[phrase] = (rank, count)
        return sorted(min_phrases.items(), key=lambda x: x[1][0], reverse=True)
    
    def increment_edge (self,graph, node0, node1):        
        if graph.has_edge(node0, node1):
            graph[node0][node1]["weight"] += 1.0
        else:
            graph.add_edge(node0, node1, weight=1.0)

    
    def link_sentence (self, doc, sent, lemma_graph, seen_lemma,POS_KEPT):
        visited_tokens = []
        visited_nodes = []

        for i in range(sent.start, sent.end):
            token = doc[i]

            if token.pos_ in POS_KEPT:
                key = (token.lemma_, token.pos_)

                if key not in seen_lemma:
                    seen_lemma[key] = set([token.i])
                else:
                    seen_lemma[key].add(token.i)

                node_id = list(seen_lemma.keys()).index(key)

                if not node_id in lemma_graph:
                    lemma_graph.add_node(node_id)
                
                for prev_token in range(len(visited_tokens) - 1, -1, -1):                    
                    if (token.i - visited_tokens[prev_token]) <= 3:
                        self.increment_edge(lemma_graph, node_id, visited_nodes[prev_token])
                    else:
                        break

                visited_tokens.append(token.i)
                visited_nodes.append(node_id)

    
    def collect_phrases (self, doc,seen_lemma, ranks, chunk, phrases, counts):
        chunk_len = chunk.end - chunk.start
        sq_sum_rank = 0.0
        non_lemma = 0
        compound_key = set([])

        for i in range(chunk.start, chunk.end):
            token = doc[i]
            key = (token.lemma_, token.pos_)
            
            if key in seen_lemma:
                node_id = list(seen_lemma.keys()).index(key)
                rank = ranks[node_id]
                sq_sum_rank += rank
                compound_key.add(key)            
            else:
                non_lemma += 1
        
        # although the noun chunking is greedy, we discount the ranks using a
        # point estimate based on the number of non-lemma tokens within a phrase
        non_lemma_discount = chunk_len / (chunk_len + (2.0 * non_lemma) + 1.0)

        # use root mean square (RMS) to normalize the contributions of all the tokens
        phrase_rank = math.sqrt(sq_sum_rank / (chunk_len + non_lemma))
        phrase_rank *= non_lemma_discount

        # remove spurious punctuation
        phrase = chunk.text.lower().replace("'", "")

        # create a unique key for the the phrase based on its lemma components
        compound_key = tuple(sorted(list(compound_key)))
        
        if not compound_key in phrases:
            phrases[compound_key] = set([ (phrase, phrase_rank) ])
            counts[compound_key] = 1
        else:
            phrases[compound_key].add( (phrase, phrase_rank) )
            counts[compound_key] += 1
