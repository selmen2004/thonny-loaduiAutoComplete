import os
from tkinter import messagebox
from logging import getLogger,DEBUG
from thonny.plugins.autocomplete import Completer, CompletionsBox ,_is_python_name_char,control_is_pressed,command_is_pressed,alt_is_pressed_without_char
import tkinter as tk
import re
from thonny.languages import tr

from thonny import editor_helpers, get_runner, get_workbench
from thonny.common import InlineCommand, CompletionInfo
from thonny.codeview import CodeViewText, SyntaxText
from thonny.shell import ShellText
from xml.dom import minidom


logger = getLogger(__name__)
logger.setLevel(logger.disabled)

WIDGET_CACHE = {}
last_editor = editor_helpers.get_active_text_widget()
# Ensemble des méthodes prioritaires
PRIORITIZED_METHODS = {
    "setText", "text", "clear", "toPlainText",
    "currentText", "isChecked", "addItem", "setItem", "insertRow"
}

# Explications en français des méthodes prioritaires


CLASS_METHOD_EXPLANATIONS = {
    "QLabel": {
        "setText": "Modifie le texte de l’étiquette."
    },
    "QTextEdit": {
        "toPlainText": "Renvoie le texte contenu dans le champ de texte",
        "setText": "Modifie le texte du champ par celui en argument.",
        "clear": "Efface le contenu du champ de texte."
    },
    "QLineEdit": {
        "text": "Renvoie le texte contenu dans le champ de texte",
        "setText": "Modifie le contenu du champ de texte par le texte fourni en argument.",
        "clear": "Efface le contenu du champ de texte."
    },
    "QPushButton": {
        "clicked": "Déclenche une action ou un évènement spécifique lorsqu'il est pressé (cliqué).",
        "connect": "Permet de connecter une fonction à un événement."
    },
    "QComboBox": {
        "currentText": "Retourne la chaîne de caractères actuellement sélectionnée."
    },
    "QRadioButton": {
        "isChecked": "Renvoie Vrai si ce bouton spécifique est sélectionné, sinon Faux."
    },
    "QCheckBox": {
        "isChecked": "Renvoie Vrai si la case est cochée sinon elle retourne Faux."
    },
    "QListWidget": {
        "addItem": "Ajoute un objet ou une chaîne à la liste",
        "clear": "Vide la liste"
    },
    "QTableWidget": {
        "setItem": "Ajoute des données à une table",
        "insertRow": "Insère une ligne"
    },
    "QTableWidgetItem": {
        "": "Ajoute un contenu à une cellule"
    },
    "QMessageBox": {
        "critical": "Affiche un message d’erreur"
    }
}


PRIORITIZED_EXPLANATIONS = {
    "setText": "Définit le texte affiché par le widget.",
    "text": "Retourne le texte actuellement affiché par le widget.",
    "clear": "Efface le contenu du widget.",
    "toPlainText": "Retourne le texte brut du widget, sans mise en forme.",
    "currentText": "Retourne le texte actuellement sélectionné dans le widget.",
    "isChecked": "Indique si le widget (ex. une case à cocher) est activé.",
    "addItem": "Ajoute un nouvel élément à la liste du widget.",
    "setItem": "Définit l'élément à une position donnée dans le widget.",
    "insertRow": "Insère une nouvelle ligne dans un widget de type tableau."
}

def parse_ui_file(source: str, row: int):
    """
    Recherche un appel à loadUi dans le code source.
    Remplace loadUi par loadX et injecte la classe Fenetre avec les widgets du fichier UI.
    Prend en charge les chemins relatifs pour les fichiers UI.
    
    Retourne :
        - source modifié
        - nombre de lignes injectées (0 ici)
        - liste des widgets détectés (nom, classe).
    """
    
    lines = source.splitlines()
    filename = None
    new_lines = []
    injected_lines_count = 0
    widget_suggestions = []
    
    # Obtenir le fichier source actuel pour résoudre les chemins relatifs
    active_editor = get_workbench().get_editor_notebook().get_current_editor()
    current_file_dir = ""
    if active_editor and active_editor.get_filename():
        current_file_dir = os.path.dirname(os.path.abspath(active_editor.get_filename()))
    
    for i, line in enumerate(lines):
        if "loadUi" in line and "PyQt5.uic" not in line:
            start = line.find("loadUi") + 6
            while start < len(line) and line[start] not in ('"', "'"):
                start += 1
            end = start + 1
            while end < len(line) and line[end] not in ('"', "'"):
                end += 1
            if end - start > 2:
                filename = line[start+1:end]
            modified_line = line.replace("loadUi", "loadX")
            new_lines.append("def loadX(file) -> Fenetre:")
            new_lines.append("    return loadUi(file)")
            new_lines.append(modified_line)
        else:
            new_lines.append(line)
    
    # Génération de la classe Fenetre
    class_def = "from PyQt5.QtWidgets import *\nfrom PyQt5.QtCore import *\n\nclass Fenetre(QDialog):"
    if filename and filename.endswith(".ui"):
        # Résoudre le chemin du fichier UI
        if not os.path.isabs(filename) and current_file_dir:
            # C'est un chemin relatif, on le résout par rapport au fichier courant
            ui_path = os.path.join(current_file_dir, filename)
            ui_path = os.path.normpath(ui_path)
        else:
            # C'est déjà un chemin absolu ou on ne peut pas déterminer le répertoire courant
            ui_path = os.path.abspath(filename)
        
        logger.debug(f"Trying to parse UI file: {ui_path}")
        
        # Vérifier si le fichier existe
        if not os.path.isfile(ui_path):
            logger.warning(f"UI file not found: {ui_path}")
            # On ajoute un commentaire pour informer l'utilisateur
            class_def += f"\n    # Avertissement: Le fichier UI '{filename}' n'a pas été trouvé."
        else:
            if ui_path not in WIDGET_CACHE:
                try:
                    xml_doc = minidom.parse(ui_path)
                    widgets = xml_doc.getElementsByTagName('widget')
                    for w in widgets[1:]:  # On saute le premier widget (formulaire principal)
                        widget_name = w.getAttribute('name')
                        widget_class = w.getAttribute('class')
                        if widget_name and widget_class:
                            class_def += f"\n    {widget_name}: {widget_class}"
                            widget_suggestions.append((widget_name, widget_class))
                    WIDGET_CACHE[ui_path] = widget_suggestions
                    WIDGET_CACHE["last"] = widget_suggestions
                except Exception as e:
                    logger.error(f"Error parsing UI file: {e}")
                    class_def += f"\n    # Erreur lors de l'analyse du fichier UI: {str(e)}"
            else:
                widget_suggestions = WIDGET_CACHE[ui_path]
                for w in widget_suggestions:
                    widget_name = w[0]
                    widget_class = w[1]
                    if widget_name and widget_class:
                        class_def += f"\n    {widget_name}: {widget_class}"
    
    new_lines.append(class_def)
    modified_source = "\n".join(new_lines)
    
    return modified_source, injected_lines_count, widget_suggestions
class CompletionsBoxWithPyQt(CompletionsBox):
    

    def __init__(self, completer: "CompleterWithPyQt") -> None:
        super().__init__(completer)
        get_workbench().bind("get_completion_details_response", self._handle_details_response, False)
        self._listbox.bind("<<ListboxSelect>>", self._on_select_item_via_event, False)
        self._completer = completer

    # pour ignorer le paramètre edit.automatic_completions
    
    
    
    def _handle_details_response(self, msg) -> None:
        global last_editor
        if not self.is_visible():
            return
        error = getattr(msg, "error", None)
        if error:
            messagebox.showerror(tr("Error"), str(error), master=get_workbench())
            return
        completion = self._get_current_completion()
        if completion.full_name != msg.full_name:
            return
        if not msg.details:
            logger.debug("Could not get details for %s", completion.full_name)
            return

        assert isinstance(msg.details, CompletionInfo)
        
        # Tenter d'extraire le contexte actuel
        widget_class = None
        current_widget_name = None
        
        # Vérifier si le nom de complétion actuel est un widget
        if "last" in WIDGET_CACHE and WIDGET_CACHE["last"]:
            for name, cls in WIDGET_CACHE["last"]:

                if name == completion.name:
                    current_widget_name = name
                    widget_class = cls
                    break
        else:
            logger.debug("No last widget cache found")
        
        # Vérifier si nous sommes en train de compléter une méthode d'un widget
        if not widget_class:
            #print("No widget class found in cache, checking active text widget")
            if last_editor and not editor_helpers.get_active_text_widget():
                text_widget =  last_editor
            else:
                text_widget = editor_helpers.get_active_text_widget()
            
            if text_widget:
                last_editor = text_widget
                current_line = text_widget.get("insert linestart", "insert")
                #print(f"Current line: '{current_line}'")
                pattern = r'(\w+)\.([^.()\s]+)\.$'
                matches = list(re.finditer(pattern, current_line))
                
                if matches:
                    last_match = matches[-1]
                    container, widget_name = last_match.groups()
                    current_widget_name = widget_name
                    
                    if "last" in WIDGET_CACHE and WIDGET_CACHE["last"]:
                        for name, cls in WIDGET_CACHE["last"]:
                            if name == current_widget_name:
                                widget_class = cls
                                break
            else:
                print("No active text widget found")
        
        # Pour le débogage
        #print(f"Widget détecté: '{current_widget_name}', Classe: '{widget_class}'")
        #print(f"Complétion actuelle: '{completion.name}'")
        
        # Déterminer l'explication
        explanation = None
        
        if widget_class:
            if completion.name == current_widget_name:
                # Si la complétion est le nom du widget lui-même, afficher des infos sur la classe
                useful_methods = []
                if widget_class in CLASS_METHOD_EXPLANATIONS:
                    useful_methods = list(CLASS_METHOD_EXPLANATIONS[widget_class].keys())
                
                explanation = f"**Widget {widget_class}**\n\n"
                explanation += f"Ce widget fait partie de l'interface utilisateur PyQt5.\n\n"
                
                if useful_methods:
                    explanation += "**Méthodes utiles:**\n"
                    for method in useful_methods:
                        method_desc = CLASS_METHOD_EXPLANATIONS[widget_class].get(method, "")
                        explanation += f"- `{method}`: {method_desc}\n"
                else:
                    explanation += "_Aucune méthode spécifique documentée pour ce widget._"
            
            elif widget_class in CLASS_METHOD_EXPLANATIONS and completion.name in CLASS_METHOD_EXPLANATIONS[widget_class]:
                explanation = CLASS_METHOD_EXPLANATIONS[widget_class][completion.name]
            elif completion.name in PRIORITIZED_EXPLANATIONS:
                explanation = PRIORITIZED_EXPLANATIONS[completion.name]
            else:
                explanation = msg.details.docstring
        else:
            explanation = msg.details.docstring

        self._details_box.set_content(
            msg.details.name,
            msg.details.type if not widget_class else f"{widget_class} widget",
            msg.details.signatures,
            explanation
        )

    
class CompleterWithPyQt(Completer):
    
    def __init__(self):
        super().__init__()
        
        self._widget_suggestions = None
        get_workbench().bind(
            "editor_autocomplete_response", self._handle_completions_response, False
        )
        
    def _should_open_box_automatically(self, event):
        assert isinstance(event.widget, tk.Text)
        
        # Don't autocomplete in remote shells
        proxy = get_runner().get_backend_proxy()
        if isinstance(event.widget, ShellText) and (not proxy or not proxy.has_local_interpreter()):
            return False

        # Don't autocomplete inside comments
        line_prefix = event.widget.get("insert linestart", "insert")
        if "#" in line_prefix:
            # not very precise (eg. when inside a string), but good enough
            return False

        return True
    # pour ignorer le paramètre edit.automatic_completion_details
    def _check_request_details(self) -> None:
        if not self.winfo_ismapped():
            # can happen, see https://github.com/thonny/thonny/issues/2162
            return
        self.request_details()
        
    def request_completions_for_text(self, text: SyntaxText) -> None:
        source, row, column = editor_helpers.get_relevant_source_and_cursor_position(text)
        modified_source, injected_lines, widget_suggestions = parse_ui_file(source, row)
        self._widget_suggestions = widget_suggestions
        #new_row = row + injected_lines
        get_runner().send_command(
            InlineCommand(
                "editor_autocomplete",
                source=modified_source,
                row=row,
                column=column,
                filename=editor_helpers.get_text_filename(text),
            )
        )
        
    def _handle_completions_response(self, msg) -> None:
        #print(msg)
        text = editor_helpers.get_active_text_widget()
        if not text:
            #print("No active text widget")
            return
        if msg.get("error"):
            #print(msg["error"])
            self._close_box()
            #tk.messagebox.showerror("Erreur d'autocomplétion", msg["error"], master=get_workbench())
            return
        if not msg["completions"]:
            #print("No completions")
            #self._close_box()
            return

        # Récupère les noms des widgets pour les prioriser
        widget_names = {w[0] for w in getattr(self, "_widget_suggestions", [])}

        # Ajustement du prefix_length pour assurer la sélection correcte
        line_start_text = text.get("insert linestart", "insert")
        m = re.search(r"(\w+)$", line_start_text)
        prefix = m.group(1) if m else ""
        prefix_length = len(prefix)

        # Réorganisation des complétions
        prioritized = []
        others = []
        for comp in msg["completions"]:
            if comp.name in widget_names or comp.name in PRIORITIZED_METHODS:
                prioritized.append(comp)
            else:
                others.append(comp)
        msg["completions"] = prioritized + others

        if not self._completions_box:
            self._completions_box = CompletionsBoxWithPyQt  (self)
        self._completions_box.present_completions(text, msg["completions"])


def load_plugin() -> None:
    # Check if another autocomplete plugin is already loaded
    for command in get_workbench()._commands:
        #print("Checking command:", command)
        if command["command_id"] == "autocomplete" and command["handler"].__module__ != __name__:
            # If found, unbind the other plugin's handlers
            logger.info("Removing existing autocomplete plugin")
            get_workbench().unbind("editor_autocomplete_response", command["handler"])
            get_workbench().unbind("shell_autocomplete_response", command["handler"])
            get_workbench().unbind("get_completion_details_response")
            
            # Remove the existing command
            del command
            break

    completer = CompleterWithPyQt()
    
    # Remplace le handler de l'autocomplétion par défaut
    get_workbench().bind("editor_autocomplete_response", completer._handle_completions_response, False)

    def can_complete():
        runner = get_runner()
        return runner and not runner.is_running()

    get_workbench().add_command(
        "autocomplete",
        "edit",
        "Auto-complete-with-pyqt-support",
        completer.request_completions,
        default_sequence="<Control-space>",
        tester=can_complete,
    )
    

    CodeViewText.perform_midline_tab = completer.patched_perform_midline_tab
    ShellText.perform_midline_tab = completer.patched_perform_midline_tab
