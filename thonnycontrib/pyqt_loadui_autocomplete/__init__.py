from thonny.plugins.autocomplete import Completer,CompletionsBox
import tkinter as tk
from thonny import editor_helpers, get_runner,get_workbench
from thonny.common import CompletionInfo, InlineCommand
from thonny.codeview import CodeViewText, SyntaxText
from thonny.shell import ShellText
from xml.dom import minidom
def parseUiFile(source:str,row:int):
        lines =source.splitlines()
        filename =''
        source = ''
        addtwo = False
        for l in lines:
            
            if "loadUi" in l :
                start= l.find("loadUi")+6
                while start <len(l) and l[start] !="\"" and l[start] !="'"  :
                    start+=1
                end =start+1
                while end <len(l) and l[end] !="\"" and l[end] !="'"  :
                    end+=1
                if end - start >2:
                    #at least 3 : 1.ui
                    filename = l[start+1:end]
                if "PyQt5.uic" not in l:
                    l= l.replace("loadUi","loadX")
                    l= "def loadX(file)->Fenetre :\r\n    return loadUi(file)\r\n"+l
                    if row >0:
                        addtwo = True
            source += l + "\r\n"
            row -= 1
        print(filename)
        textToAdd =  "\r\nfrom PyQt5 import *\r\nfrom PyQt5.QtWidgets import *\r\nfrom PyQt5.QtCore import *\r\nDialog = QtWidgets.QDialog()\r\n"+ "class Fenetre (QDialog):" 
        if filename!= '':
            file = minidom.parse(filename)
            widgets = file.getElementsByTagName('widget')
           
            for w in widgets:
                textToAdd +="\r\n    "+w.attributes['name'].value +" : "+w.attributes['class'].value 
                # elems.append(CompletionInfo(name=w.attributes['name'].value
                # ,name_with_symbols=w.attributes['name'].value
                # ,full_name=w.attributes['name'].value,
                # type=w.attributes['class'].value,
                # signatures = None,
                # prefix_length = 0,
                # docstring ="PyQt Widget"
                # ))
        #print(source+textToAdd)
        return (source+textToAdd,addtwo)
class Completer_with_pyqt(Completer):
    """
    Manages completion requests and responses.
    Delegates user interactions with completions to CompletionsBox.
    """
    
    def request_completions_for_text(self, text: SyntaxText) -> None:
        source, row, column = editor_helpers.get_relevant_source_and_cursor_position(text)
        # textToAdd=''
        # if "loadUi" in source :
        #     lines =source.splitlines()
        #     filename =''
            
        #     for l in lines:
        #         if "loadUi" in l :
        #             start= l.find("loadUi")+6
        #             while start <len(l) and l[start] !="\"" and l[start] !="'"  :
        #                 start+=1
        #             end =start+1
        #             while end <len(l) and l[end] !="\"" and l[end] !="'"  :
        #                 end+=1
        #             if end - start >2:
        #                 #at least 3 : 1.ui
        #                 filename = l[start+1:end]
        #     #print(filename)
        #     if filename!= '':
        #         from  PyQt5.uic import compileUi
        #         import os
        #         py_path = "tmp150911986.py"
        #         py_file = open(py_path,"w")
        #         ui_file = open(filename,"r")
        #         try:
        #             compileUi(ui_file, py_file)
                
        #         finally:
        #             ui_file.close()
        #             py_file.close()
        #         textToAdd+="\r\nfrom PyQt5 import *\r\nfrom PyQt5.QtWidgets import *\r\nfrom PyQt5.QtCore import *\r\nDialog = QtWidgets.QDialog()\r\n"
        #         generatedFile = open(py_path,"r").read()
        #         lines = generatedFile.splitlines()
        #         started = False
        #         ended = False
        #         for l in lines:
                    
        #             if "setupUi" in l:
        #                 started = True
        #             if started and not ended and "self." in l and not "retranslateUi" in l:
        #                 l = l.strip().replace("self","windows")
        #                 textToAdd += ("\r\n"+l)
        #             if "retranslateUi" in l:
        #                 ended = True

                        

                
                
                
                
                
                
                #textToAdd+="from PyQt5 import *\r\nfrom PyQt5.QtWidgets import *\r\nfrom QtCore import *\r\n"
                #textToAdd += "\n\rDialog = QtWidgets.QDialog()\n\rwindows = Ui_Dialog()\n\rwindows.setupUi(Dialog)"
                #print(source+"\r\n"+textToAdd)

                #os.remove(py_path)
            
        inf = parseUiFile(source,row)
        if inf[1]:
            row = row+2
        
        get_runner().send_command(
            InlineCommand(
                "shell_autocomplete" if isinstance(text, ShellText) else "editor_autocomplete",
                source=inf[0],
                row=row,
                column=column,
                filename=editor_helpers.get_text_filename(text),
            )
        )
                

                
            
    

  
    def _handle_completions_response(self, msg) -> None:
        text = editor_helpers.get_active_text_widget()
        if not text:
            return
        
        source, row, column = editor_helpers.get_relevant_source_and_cursor_position(text)
        
        print("msg:",msg)
        if msg.get("error"):
            self._close_box()
            messagebox.showerror("Autocomplete error", msg.error, master=get_workbench())
        elif msg.source != parseUiFile(source,0)[0] or msg.column != column:
            # situation has changed, information is obsolete
            # ignore this event
            return
        elif not msg.completions:
            # the user typed something which is not completable
            self._close_box()
            return
        else:
            # if("PyQt5.uic" in source):
            #     pl = msg.completions[0].prefix_length
            #     for el in self.parseUiFile(source):
            #         el.prefix_length  = pl
            #         msg.completions.insert(0,el)

            if not self._completions_box:
                self._completions_box = CompletionsBox(self)
            self._completions_box.present_completions(text, msg.completions)
            

    def patched_perform_midline_tab(self, event):
        if not event or not isinstance(event.widget, SyntaxText):
            return
        text = event.widget

        if text.is_python_text():
            if isinstance(text, ShellText):
                option_name = "edit.tab_request_completions_in_shell"
            else:
                option_name = "edit.tab_request_completions_in_editors"

            if get_workbench().get_option(option_name):
                if not text.has_selection():
                    self.request_completions_for_text(text)
                    return "break"
                else:
                    return None

        return text.perform_dumb_tab(event)


def _is_python_name_char(c: str) -> bool:
    return c.isalnum() or c == "_"


def load_plugin() -> None:

    completer = Completer_with_pyqt()
    def can_complete():
        runner = get_runner()
        return runner and not runner.is_running()
    get_workbench().unbind("<Control-space>")
    get_workbench().add_command(
        "autocomplete",
        "edit",
        ("Auto-complete-with-pyqt-support"),
        completer.request_completions,
        default_sequence="<Control-space>",
        tester=can_complete,
    )

    

    CodeViewText.perform_midline_tab = completer.patched_perform_midline_tab
    ShellText.perform_midline_tab = completer.patched_perform_midline_tab
    
