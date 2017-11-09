from z3 import *
from mythril.analysis import solver
from mythril.analysis.ops import *
from mythril.analysis.report import Issue
from mythril.exceptions import UnsatError
import re
import logging



'''
MODULE DESCRIPTION:

Check for SUICIDE instructions that either can be reached by anyone, or where msg.sender is checked against a tainted storage index 
(i.e. there's a write to that index is unconstrained by msg.sender).
'''

def execute(statespace):

    issues = []

    for k in statespace.nodes:
        node = statespace.nodes[k]

        for instruction in node.instruction_list:

            if(instruction['opcode'] == "SUICIDE"):

                logging.debug("[UNCHECKED_SUICIDE] suicide in function " + node.function_name)

                issue = Issue("Unchecked SUICIDE", "Warning")
                issue.description = "The function " + node.function_name + " executes the SUICIDE instruction."

                state = node.states[instruction['address']]
                to = state.stack.pop()

                if ("caller" in str(to)):
                    issue.description += "\nThe remaining Ether is sent to the caller's address.\n"
                elif ("storage" in str(to)):
                    issue.description += "\nThe remaining Ether is sent to a stored address\n"
                elif ("calldata" in str(to)):
                    issue.description += "\nThe remaining Ether is sent to an address provided as a function argument."
                elif (type(to) == BitVecNumRef):
                    issue.description += "\nThe remaining Ether is sent to: " + hex(to.as_long())
                else:
                    issue.description += "\nThe remaining Ether is sent to: " + str(to) + "\n"

                constrained = False
                can_solve = True

                while (can_solve and len(node.constraints)):

                    constraint = node.constraints.pop()

                    m = re.search(r'storage_([a-z0-9_&^]+)', str(constraint))

                    overwrite = False

                    if (m):
                        constrained = True
                        index = m.group(1)

                        try:

                            for s in statespace.sstors[index]:

                                if s.tainted:
                                    issue.description += "\nThere is a check on storage index " + str(index) + ". This storage index can be written to by calling the function '" + s.node.function_name + "'."
                                    break

                            if not overwrite:
                                logging.debug("[UNCHECKED_SUICIDE] No storage writes to index " + str(index))
                                can_solve = False
                                break

                        except KeyError:
                            logging.debug("[UNCHECKED_SUICIDE] No storage writes to index " + str(index))
                            can_solve = False
                            break


                    # CALLER may also be constrained to hardcoded address. I.e. 'caller' and some integer

                    elif (re.search(r"caller", str(constraint)) and re.search(r'[0-9]{20}', str(constraint))):
                       can_solve = False
                       break


                if not constrained:
                    issue.description += "\nIt seems that this function can be called without restrictions."

                if can_solve:

                    try:
                        model = solver.get_model(node.constraints)
                        issues.append(issue)

                        for d in model.decls():
                            logging.debug("[UNCHECKED_SUICIDE] main model: %s = 0x%x" % (d.name(), model[d].as_long()))
                    except UnsatError:
                            logging.debug("[UNCHECKED_SUICIDE] no model found")         

    return issues
