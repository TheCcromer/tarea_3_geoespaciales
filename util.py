import unidecode
import unicodedata

def corregir_acentos(texto):
    try:
        return texto.encode('latin1').decode('utf-8')
    except Exception:
        return texto

def remover_acentos(input_str):
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nkfd_form.encode('ASCII', 'ignore')
    return only_ascii.decode('utf-8')