import logging
import os

from config import cfg
from datetime import datetime
from db import DB
from extract import extract
import items
import utils as u


LOG = logging.getLogger(__name__)


class Parser():
    def __init__(self):
        self.data_root = cfg['main']['data_dir']
        self.h_index_fname = cfg['advanced']['h_index_file']
        self.db = DB(cfg['advanced']['db_file'])

    def update(self):
        get_idx = lambda dname: int(dname[7:])

        listing = sorted((fn for fn in os.listdir(self.data_root)
                          if fn.startswith('datadir')),
                         key=get_idx)
        cur_datadir_idx = get_idx(self.db['cur_datadir'])

        for datadir in u.full_circle(listing, cur_datadir_idx):
            self.update_datadir(datadir)

    def update_datadir(self, datadir):
        LOG.info('Entering {}'.format(datadir))

        h_idx_file = items.IndexFile(os.path.join(self.data_root,
                                                  datadir,
                                                  self.h_index_fname))
        h_idx_file_rev = h_idx_file.header.revision

        LOG.info('Index revision is {}'.format(h_idx_file_rev))

        db_dir_entry = self.db['datadirs'][datadir]

        # Skip if revision has not changed
        if db_dir_entry['revision'] == h_idx_file_rev:
            LOG.info('Revision unchanged, nothing to update')
            return

        cur_sec_idx = db_dir_entry['cur_section']
        for sec in u.full_circle(h_idx_file.sections, cur_sec_idx):

            LOG.debug('Entering section {}'.format(sec.idx))

            if sec.idx == cur_sec_idx:
                next_vrec_idx = db_dir_entry['last_vrec'] + 1
            else:
                next_vrec_idx = 0

            next_vrecs = u.islice_from(sec.video_records, next_vrec_idx)
            for i, vrec in enumerate(next_vrecs):
                if vrec.start_dt == datetime.utcfromtimestamp(0):
                    LOG.debug('Skipping extraction of incomplete vrec'
                              'at {}:{:x}'.format(vrec._h_idx_file.name, vrec._pos))
                    continue
                try:
                    extract(vrec)
                    db_dir_entry['last_vrec'] = next_vrec_idx + i
                    db_dir_entry['cur_section'] = sec.idx
                    self.db['cur_datadir'] = datadir
                    self.db.save()
                except FileExistsError as e:
                    LOG.info('File {} exists, will not overwrite'
                              .format(e.filename))

        LOG.info('Done processing revision {}'
                 .format(h_idx_file_rev))
        db_dir_entry['revision'] = h_idx_file_rev
        self.db.save()
