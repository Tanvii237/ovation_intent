import os
import datasets
import collections


class STS(object):
    def __init__(self, train_validation_split=None, test_split=None,
                 use_defaults=True, subset='sts_small'):
        if train_validation_split is not None or test_split is not None or \
                use_defaults is False:
            raise NotImplementedError('This Dataset does not implement '
                  'train_validation_split, test_split or use_defaults as the '
                  'dataset is big enough and uses dedicated splits from '
                  'the original datasets')
        self.dataset_name = 'Semantic Text Similarity - All'
        self.dataset_description = 'This dataset has been generated by ' \
               'merging MPD, SICK, Quora, StackExchange and and SemEval ' \
               'datasets. \n It has 258537 Training sentence pairs, 133102 ' \
               'Test sentence pairs and 59058 validation sentence pairs.'
        self.test_split = 'large'
        self.dataset = subset
        #self.dataset_path = os.path.join(datasets.data_root_directory, self.dataset)
        self.dataset_path = os.path.join('/','home', 'tanvi', 'dataset', 'quora')
        self.train_path = os.path.join(self.dataset_path, 'train', 'dep_train.txt')
        self.validation_path = os.path.join(self.dataset_path, 'validation',
                                            'dep_validation.txt')
        self.test_path = os.path.join(self.dataset_path, 'test', 'dep_test.txt')
        self.vocab_path = os.path.join(self.dataset_path, 'vocab.txt')
        self.metadata_path = os.path.abspath(os.path.join(self.dataset_path,
                                               'metadata.txt'))
        self.w2v_path = os.path.join(self.dataset_path, 'w2v.npy')

        self.w2i, self.i2w = datasets.load_vocabulary(self.vocab_path)
        self.w2v = datasets.load_w2v(self.w2v_path)

        self.vocab_size = len(self.w2i)
        self.train = DataSet(self.train_path, (self.w2i, self.i2w))
        self.validation = DataSet(self.validation_path, (self.w2i, self.i2w))
        self.test = DataSet(self.test_path, (self.w2i, self.i2w))
        self.__refresh(load_w2v=False)

    def create_vocabulary(self, min_frequency=5, tokenizer='spacy',
                          downcase=False, max_vocab_size=None,
                          name='new', load_w2v=True):
        self.vocab_path, self.w2v_path, self.metadata_path = \
            datasets.new_vocabulary([self.train_path], self.dataset_path,
                                    min_frequency, tokenizer=tokenizer, downcase=downcase,
                                    max_vocab_size=max_vocab_size, name=name)
        self.__refresh(load_w2v)

    def __refresh(self, load_w2v):
        self.w2i, self.i2w = datasets.load_vocabulary(self.vocab_path)
        self.vocab_size = len(self.w2i)
        if load_w2v:
            self.w2v = datasets.preload_w2v(self.w2i)
            datasets.save_w2v(self.w2v_path, self.w2v)
        self.train.set_vocab((self.w2i, self.i2w))
        self.validation.set_vocab((self.w2i, self.i2w))
        self.test.set_vocab((self.w2i, self.i2w))


class DataSet(object):
    def __init__(self, path, vocab):

        self.path = path
        self._epochs_completed = 0
        self.vocab_w2i = vocab[0]
        self.vocab_i2w = vocab[1]
        self.datafile = None

        self.Batch = collections.namedtuple('Batch', ['s1', 's2', 'sim'])

    def open(self):
        self.datafile = open(self.path, 'r')

    def close(self):
        self.datafile.close()

    def remove_entities(self, data):
        entities = ['PERSON' , 'NORP' , 'FACILITY' , 'ORG' , 'GPE' , 'LOC' +
                    'PRODUCT' , 'EVENT' , 'WORK_OF_ART' , 'LANGUAGE' ,
                    'DATE' , 'TIME' , 'PERCENT' , 'MONEY' , 'QUANTITY' ,
                    'ORDINAL' , 'CARDINAL' , 'BOE', 'EOE']
        data_ = []
        for d in data:
            d_ = []
            for token in d:
                if token not in entities:
                    d_.append(token)
            data_.append(d_)
        return data_

    def next_batch(self, batch_size=64, seq_begin=False, seq_end=False,
                   rescale=(0.0, 1.0), pad=0, raw=False, keep_entities=False):
        if not self.datafile:
            raise Exception('The dataset needs to be open before being used. '
                            'Please call dataset.open() before calling '
                            'dataset.next_batch()')
        datasets.validate_rescale(rescale)

        s1s, s2s, sims = [], [], []

        while len(s1s) < batch_size:
            row = self.datafile.readline()
            if row == '':
                self._epochs_completed += 1
                self.datafile.seek(0)
                continue
            cols = row.strip().split('\t')
            s1, s2, sim = cols[0], cols[1], float(cols[2])
            s1, s2 = s1.split(' '), s2.split(' ')

            # convert to dependency tree

            s1s.append(s1)
            s2s.append(s2)
            sims.append(sim)

        if not keep_entities:
            s1s = self.remove_entities(s1s)
            s2s = self.remove_entities(s2s)

        if not raw:
            s1s = datasets.dep_seq2id(s1s[:batch_size], self.vocab_w2i, seq_begin,
                                  seq_end)
            s2s = datasets.dep_seq2id(s2s[:batch_size], self.vocab_w2i, seq_begin,
                                  seq_end)
        else:
            s1s = datasets.append_seq_markers(s1s[:batch_size], seq_begin, seq_end)
            s2s = datasets.append_seq_markers(s2s[:batch_size], seq_begin, seq_end)
        if pad != 0:
            s1s = datasets.padseq(s1s, pad, raw)
            s2s = datasets.padseq(s2s, pad, raw)
        batch = self.Batch(
            s1=s1s,
            s2=s2s,
            sim=datasets.rescale(sims[:batch_size], rescale, (0.0, 1.0)))
        return batch

    def set_vocab(self, vocab):
        self.vocab_w2i = vocab[0]
        self.vocab_i2w = vocab[1]

    @property
    def epochs_completed(self):
        return self._epochs_completed
