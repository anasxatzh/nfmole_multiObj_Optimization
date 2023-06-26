
import gurobipy as gp
from gurobipy import GRB
import os, csv, random
from inspect import currentframe

"""
Requirements:

Packages : gurobipy

Create a desktop folder with the name "multiObjective_Gurobi" in which the
data that is to be imported is placed.

"""



class Base(object):
    def __init__(self,
                 target_percentage : float = .7,
                 searchPath : str = r"C:\\Users\\" + str(os.getlogin()) + "\\Desktop\\multiObjective_Gurobi",
                 modelName : str = "NFMOLE",
                 minimumRows : int = 1,
                 riskIdxs : list = [],
                 realRisk : int = 0,
                 objectiveWeight : tuple = (1.0, 1.0),
                 objectiveIdx : tuple = (0,1),
                 sensitivityThreshold : float = .4
                 ) -> None:

        self.target_percentage, self.searchPath, self.modelName, \
            self.minimumRows, self.riskIdxs, self.realRisk, self.objectiveWeight, \
                    self.objectiveIdx, self.sensitivityThreshold = target_percentage, \
                        searchPath, modelName, minimumRows, riskIdxs, realRisk, \
                            objectiveWeight, objectiveIdx, sensitivityThreshold


    def queryFile(self,
                    fileName : str = "NFMOLE.csv") -> str:
        for root, _, files in os.walk(self.searchPath):
            return os.path.join(root, fileName) \
                if fileName in files else None

    @staticmethod
    def getLineNum() -> int:
        return currentframe().f_back.f_lineno



class ImportData(Base):

    def __init__(self, 
                 *args, 
                 **kwargs
                 ) -> None:
        super().__init__(*args, **kwargs)


    @staticmethod
    def get2dSample(inptList : list, 
                    rowSize : int,
                    colSize : int,
                    random_ : bool = False) -> list:

        return [random.sample(row, colSize) for row in \
                random.sample(inptList, rowSize)] if random_ else \
                [row[:colSize] for row in inptList[:rowSize]]



    def importRiskData(self) -> tuple[list, int]:

        r"""
        Import the risk data as a 2d array (list)
        [1] -> Convert the risk data to binary values based on the
               formula : 
                       value >= .5 ==> 1
                       value <  .5 ==> 0
        """

        # LOAD THE RISK DATA
        # data = [
        #         [0.1, 0.2, 0.2, 0.4],
        #         [0.8, 0.6, 0.1, 0.6],
        #         [0.2, 0.6, 0.5, 0.3],
        #         [0.4, 0.3, 0.4, 0.3],
        #         [0.1, 0.5, 0.6, 0.1]
        #        ]

        data = list(csv.reader(open(self.queryFile(), "r"), delimiter=";")
                   )

        # TAKE SAMPLE OF DATA
        data = self.get2dSample(data, 
                                rowSize = 500, 
                                colSize = 500)

        # BINARY REPRESENTATION OF RISK DATA *1
        riskD = [
                [1 if float(val) >= .5 else 0 for val in row] \
                    for row in data
                ]

        # APPLY WEIGHTS TO RISK DATA
        weights = list(csv.reader(open(self.queryFile(fileName = "weights.csv"), "r"), delimiter=";")
                      )

        ## FLATTEN WEIGHT LIST
        weights = [float(k) for k in sum(weights, [])]
        weights = weights[:len(data[0])]
        weights_ = [k/2 for k in weights] # REAL WEIGHTS ARE NOT ALL 1s


        if len(data[0]) != len(weights):\
            raise Exception("Risk data length does not match Weights length" + str(self.getLineNum()))


        ## VALIDATE ALL ELEMENTS IN 2D ARRAY ARE BINARY
        assert len(
                   [elem for r in range(len(riskD)) for elem in riskD[r] \
                    if elem in (1,0)]
                  ) == len([it for item in riskD for it in item]),\
                  "Risk Data is not binary!\nLine --> " + str(self.getLineNum())

        return [
                [riskD[r][v] * weights[v] for v in range(len(riskD[r]))]\
                for r in range(len(riskD))
               ], sum(weights_)





class ApplyOpt(ImportData):

    def __init__(self, 
                 *args, 
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)



    def applySolution(self) -> None:

        r"""
        [1] -> selected_rows : dict
               Of type : {0 : "gurobiVar_0, 1 : "gurobiVar_1, ...}
               len(selected_rows) == len(riskData)

        [2] -> If a row is selected then all previous rows must 
               also be selected for each column.
        """

        (riskData,
         total_data_weighted_sum
        ) = self.importRiskData() # BINARY

        numRows : int = len(riskData)


        # CREATE THE MODEL
        model = gp.Model(self.modelName)

        # ADD VARIABLES
        ## *1
        selected_rows = model.addVars(numRows,
                                      name = "selected_rows",
                                      vtype = GRB.BINARY)


        ## SET MODEL SENSE --> BY DEFAULT MINIMIZE

        targetRisk = sum(
                     [
                      sum(
                          riskData[i][j] * selected_rows[i] for i in range(numRows) \
                          if not any(riskData[l][j] == 1 for l in range(i))
                        #   if not any(riskData[l][j] == 1 for l in range(int(self.sensitivityThreshold * i), i))
                          )\
                      for j in range(len(riskData[0]))
                     ]
                    )

        print("TARGET IS ", self.target_percentage * total_data_weighted_sum)

        # SET OBJECTIVE FUNCTIONS
        model.setObjectiveN(targetRisk,
                            index = self.objectiveIdx[0],
                            weight = self.objectiveWeight[0],
                            name = "maxRisk")

        model.setObjectiveN(sum(selected_rows),
                            index = self.objectiveIdx[1],
                            weight = -1.0 * self.objectiveWeight[1],
                            name = "minRows")

        print("4")
        # ADD CONSTRAINTS TO THE MODEL
        ## *2
        for row in range(1,numRows):
            model.addConstr(selected_rows[row] <= selected_rows[row-1],
                            name = "incrementRows"
                        )

        model.addConstr(sum(selected_rows[row] \
                            for row in range(numRows)) >= self.minimumRows,
                        name="min_selected_rows"
                       )

        model.addConstr(
                        targetRisk >= self.target_percentage * total_data_weighted_sum,
                        name="target_percentage"
                       )

        print("before optimization")
        # OPTIMIZE THE MODEL
        model.optimize()
        print("after optimization")

        self.getSolution(model = model)





    def getSolution(self,
                    model : "GRBModel") -> None:

        if model.status == GRB.OPTIMAL:

            decision = model.getAttr('x')
            model.printAttr(['x'])
            model.printAttr(['Sense', 'Slack', 'RHS'])

        else:
            print("NO OPTIMAL SOLUTION FOUND!")







if __name__ == "__main__":

    applyOpt = ApplyOpt()
    applyOpt.applySolution()








































































