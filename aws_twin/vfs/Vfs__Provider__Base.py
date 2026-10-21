"""The provider contract, mirrored from sg-vfs-provider-base.js (SGraph-AI__Tools, sg-vfs
v0.1.0) so a Python provider and a JavaScript provider are interchangeable layers.

Differences, deliberate: Python is synchronous (botocore is), and file content is bytes
(S3 objects are bytes). A JavaScript layer that stores strings holds base64."""


class Vfs__Provider__Base:
    name = 'base'

    def init(self):                                  pass
    def read_file    (self, path: str) -> bytes:     raise NotImplementedError(f'{self.name}.read_file')
    def write_file   (self, path: str, content: bytes): raise NotImplementedError(f'{self.name}.write_file')
    def delete_file  (self, path: str):              raise NotImplementedError(f'{self.name}.delete_file')
    def list_folder  (self, path: str) -> list:      raise NotImplementedError(f'{self.name}.list_folder')
    def stat         (self, path: str) -> dict:      raise NotImplementedError(f'{self.name}.stat')
    def create_folder(self, path: str):              raise NotImplementedError(f'{self.name}.create_folder')
    def copy_file    (self, src: str, dst: str):     raise NotImplementedError(f'{self.name}.copy_file')
    def rename       (self, src: str, dst: str):     raise NotImplementedError(f'{self.name}.rename')
    def exists       (self, path: str) -> bool:      raise NotImplementedError(f'{self.name}.exists')

    def walk_files(self, path: str = '/'):
        """Every file under path, depth first; built on list_folder so every provider has it."""
        for entry in self.list_folder(path):
            if entry['type'] == 'folder':
                yield from self.walk_files(entry['path'])
            else:
                yield entry
