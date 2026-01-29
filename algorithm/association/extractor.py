"""
Association Analysis Parameter Extractor

关联分析参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class AssociationExtractor(BaseAlgorithmExtractor):
    """关联分析参数提取器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.ASSOCIATE
    
    @property
    def algorithm_name(self) -> str:
        return "association"
    
    async def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建关联分析参数提取提示词"""
        
        # 从NL2SQL服务获取候选表信息
        schema_text, query_db_result = await self._get_candidate_tables_from_nl2sql(question, window_id)
        
        # 保存查询结果供后续使用
        self._last_query_db_result = query_db_result
        
        system_prompt = f"""你是多元关联分析专家。根据用户问题和数据库信息,提取关联分析所需的列数据和分析模式。

重要：你必须严格按照以下规则输出JSON,确保列名完全匹配数据库中的实际列名。

多元关联分析支持三种模式：
1. bivariate(二元关联分析): 分析两个变量之间的关联关系
   - 要求：恰好2列
   - 方法：卡方检验/相关性分析/方差分析(自动选择)
   - 关键词识别：分析A和B的关系、A与B是否相关、A和B有什么关联
   
2. pairwise(多变量两两关联分析): 分析多个变量之间的两两关联关系
   - 要求：至少3列
   - 方法：互信息(MI)
   - 适用场景：找出多个变量中哪些相互关联,探索性分析
   - 关键词识别：
     * "A、B、C之间的关联" - 没有明确的因变量
     * "哪些变量相互关联" - 探索所有变量的关系
     * "分析多个因素之间的关系" - 平等对待所有变量
     * "找出相关的变量" - 不区分因变量和自变量
   - 特点：所有变量地位平等,没有因变量的概念
   
3. multivariate(多变量综合关联分析): 分析多个自变量与一个因变量的综合关联
   - 要求：至少3列
   - 方法：条件互信息(CMI) + 回归分析
   - 适用场景：分析哪些因素影响某个目标变量,有明确的目标
   - 关键词识别：
     * "哪些因素与Y有关联" - Y是因变量(放第一列)
     * "Y与哪些因素存在关联性" - Y是因变量(放第一列)
     * "Y与A、B、C的关系" - Y是因变量(放第一列)
     * "A、B、C与Y的关系" - Y是因变量(放第一列)
   - 特点：有明确的因变量(目标变量),其他为自变量(影响因素)

数据库可用列信息：
{schema_text}

参数提取规则：
1. **columns**: 提取所有需要分析的列名(列表形式)
   - 必须是数据库中实际存在的列注释
   - 至少2列,可以是多列
   - 对于multivariate模式,将因变量放在第一位
   
2. **analysis_mode**: 分析模式(可选,系统可自动推断)
   - 如果用户明确表达了分析意图,则指定模式
   - 如果不确定,可以不指定,系统会根据列数自动推断
   
3. **required_columns**: 需要查询的所有列注释(与columns相同)

4. **normalized_query**: 规范化查询描述
   - 必须写明返回的数据列注释
   - 必须标明返回几列数据
   - 格式示例："获取XX年xx月到xx年月期间的历史销售数据的日期、销售额、地区,返回日期、销售额、地区共3列数据"

用户意图识别：
- "分析A和B的关系" → bivariate模式,2列
- "分析A、B、C之间的关联" → pairwise模式,3列(所有变量地位平等)
- "分析哪些因素影响D" → multivariate模式,D为因变量(第一列),其他为自变量
- "D受哪些因素影响" → multivariate模式,D为因变量(第一列)
- "分析A、B、C对D的影响" → multivariate模式,D为因变量(第一列),A、B、C为自变量
- "A、B、C和D的关联性" → multivariate模式,**D为因变量(第一列)**,A、B、C为自变量
- "A、B、C与D的关系" → multivariate模式,**D为因变量(第一列)**,A、B、C为自变量

**关键规则：当用户列举多个变量时,最后一个变量通常是因变量(目标变量)**

**重要：pairwise vs multivariate 的区分**

选择 **pairwise** 当：
- 用户想探索多个变量之间的关系,没有明确的目标变量,出现“两两”，“彼此”，“之间”等关键词
- 问题类似："A、B、C之间有什么关联？"(注意：没有第4个变量)
- 问题类似："哪些变量相互关联？"
- 问题类似："分析年龄、学历、工作年限之间的关系"(3个变量,地位平等)
- 所有变量地位平等,没有因变量

选择 **multivariate** 当：
- 用户有明确的目标变量(因变量),想知道哪些因素影响它
- 问题类似："哪些因素影响薪资？"(薪资是因变量)
- 问题类似："薪资受哪些因素影响？"(薪资是因变量)
- 问题类似："分析年龄、学历对薪资的影响"(薪资是因变量)
- 问题类似："年龄、学历、工作年限和薪资的关联"(**薪资是最后一个,作为因变量**)
- 问题类似："A、B、C与D的关系"(**D放第一列,作为因变量**)
- 问题类似："A和B、C、D的关系"(**A放第一列,作为因变量**)
- **当列举多个变量时,最后一个通常是要分析的目标变量(因变量)，此时将因变量放在第一列**

**列的顺序要求**：
- bivariate: 两列顺序任意
- pairwise: 所有列顺序任意(地位平等)
- multivariate: **必须将因变量放在第一位**,其余自变量顺序任意
  - 识别因变量：通常是用户问题中最后提到的变量
  - 例如："A、B、C和D的关联" → D是因变量,columns应为[D, A, B, C]
  - 例如："年龄、学历与薪资的关系" → 薪资是因变量,columns应为[薪资, 年龄, 学历]

输出JSON格式(严格遵守)：
{{
  "parameter_mapping": {{
    "columns": ["年龄", "学历", "工作年限", "薪资"],
    "analysis_mode": "pairwise"  // 可选,不确定可省略
  }},
  "required_columns": ["年龄", "学历", "工作年限", "薪资"],
  "normalized_query": "获取员工信息的年龄、学历、工作年限、薪资,返回年龄、学历、工作年限、薪资共4列数据，年龄放在第一列"
}}

严格输出规则：
1. **columns必须是数据库中实际存在的列注释**
   - 必须从上面提供的数据库可用列信息中选择
   - 若analysis_mode为multivariate，columns的第一个参数必须为因变量
   - 不要创造不存在的列注释
   - 优先选择有注释说明的列
2. **required_columns必须与columns完全一致**
   - required_columns中一定写明要返回的列注释
   - 必须与normalized_query中使用的名称相同
   - 示例：
     - "required_columns": ["日期", "销售额", "地区"]
     - "normalized_query": "获取XX年xx月到xx年月期间的历史销售数据的日期、销售额、地区,返回日期、销售额、地区共3列数据"
3. **normalized_query必须明确说明返回的列**
   - 必须写明返回的数据列注释(即columns中的所有列)
   - 必须标明返回几列数据
   - 格式示例：
     - "获取2023年1月到2023年12月期间的销售数据的日期、销售额,返回日期、销售额共2列数据"
     - "获取员工信息的年龄、学历、工作年限、薪资,返回年龄、学历、工作年限、薪资共4列数据"
4. **列注释的一致性**
   - columns、required_columns、normalized_query中的列名必须完全一致
   - 都使用列注释,不使用列的英文名称
   - 确保三个字段中的列名顺序一致

向后兼容性说明：
- 如果用户使用旧的二元分析表达方式,提取2列并自动设置为bivariate模式
- 系统会自动处理旧格式到新格式的转换"""
        
        user_prompt = f"""用户问题: {question}

请严格按照系统提示的规则分析用户需求,输出符合多元关联分析要求的JSON参数。

关键要求：
1. 识别用户想要分析关联的所有变量(列名)
2. 从数据库schema中找到对应的实际列注释
3. 根据用户意图判断分析模式(如果明确的话)
4. 对于multivariate模式,将因变量放在columns的第一位

输出JSON格式的参数提取结果。"""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _format_database_schema(self, database_schema: List[DatabaseColumn]) -> str:
        """格式化数据库模式信息"""
        if not database_schema:
            return "(无可用数据库模式信息)"
        
        # 按表名分组
        tables = {}
        for column in database_schema:
            table_name = column.table_name
            if table_name not in tables:
                tables[table_name] = []
            tables[table_name].append(column)
        
        # 格式化输出
        lines = []
        for table_name, columns in tables.items():
            lines.append(f"表: {table_name}")
            for column in columns:
                comment = f": {column.column_comment}" if column.column_comment else ""
                # 标记数值型列和分类型列
                numeric_types = ['int', 'integer', 'decimal', 'float', 'double', 'numeric', 'bigint', 'smallint']
                text_types = ['char', 'varchar', 'text', 'string', 'enum']
                
                if any(num_type in column.data_type.lower() for num_type in numeric_types):
                    type_mark = " [数值型]"
                elif any(text_type in column.data_type.lower() for text_type in text_types):
                    type_mark = " [文本/分类型]"
                else:
                    type_mark = ""
                
                lines.append(f"  - {column.column_name} ({column.data_type}){type_mark}{comment}")
        
        return "\n".join(lines)
    
    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)
            
            parameter_mapping = result.get('parameter_mapping', {})
            
            # 处理新格式：columns列表
            if 'columns' in parameter_mapping:
                columns = parameter_mapping['columns']
                
                # 确保columns是列表
                if not isinstance(columns, list):
                    columns = [columns]
                
                # 确保所有列名都是字符串
                columns = [str(col) for col in columns]
                parameter_mapping['columns'] = columns
                
                # 处理analysis_mode
                analysis_mode = parameter_mapping.get('analysis_mode')
                if analysis_mode:
                    # 确保是字符串且是有效值
                    analysis_mode = str(analysis_mode).lower()
                    if analysis_mode not in ['bivariate', 'pairwise', 'multivariate']:
                        logger.warning(f"无效的analysis_mode: {analysis_mode},将根据列数自动推断")
                        analysis_mode = None
                
                # 如果没有指定analysis_mode,根据列数自动推断
                if not analysis_mode:
                    if len(columns) == 2:
                        analysis_mode = 'bivariate'
                        logger.info(f"根据列数(2)自动推断为bivariate模式")
                    elif len(columns) >= 3:
                        # 默认使用pairwise模式,除非用户明确表达了因变量意图
                        analysis_mode = 'pairwise'
                        logger.info(f"根据列数({len(columns)})自动推断为pairwise模式")
                
                parameter_mapping['analysis_mode'] = analysis_mode
            
            # 处理旧格式：column1和column2(向后兼容)
            elif 'column1' in parameter_mapping and 'column2' in parameter_mapping:
                logger.info("检测到旧格式参数,自动转换为新格式")
                
                column1 = str(parameter_mapping['column1'])
                column2 = str(parameter_mapping['column2'])
                
                # 转换为新格式
                parameter_mapping['columns'] = [column1, column2]
                parameter_mapping['analysis_mode'] = 'bivariate'
                
                # 保留旧字段以保持兼容性
                parameter_mapping['column1'] = column1
                parameter_mapping['column2'] = column2
                
                logger.info(f"旧格式已转换: column1={column1}, column2={column2} -> columns=[{column1}, {column2}], mode=bivariate")
            
            else:
                raise ValueError("参数映射中既没有'columns'也没有'column1/column2'")
            

            
            result['parameter_mapping'] = parameter_mapping
            return result
            
        except Exception as e:
            logger.error(f"关联分析参数解析失败: {str(e)}")
            raise ValueError(f"关联分析参数解析失败: {str(e)}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证关联分析参数"""
        validated = {}
        
        # 验证columns列表
        columns = parameters.get('columns')
        if not columns:
            # 尝试从旧格式获取(向后兼容)
            column1 = parameters.get('column1')
            column2 = parameters.get('column2')
            if column1 and column2:
                columns = [column1, column2]
                logger.info("从旧格式(column1/column2)获取列名")
            else:
                raise ValueError("关联分析需要指定列名(columns)或使用旧格式(column1/column2)")
        
        # 确保columns是列表
        if not isinstance(columns, list):
            columns = [columns]
        
        # 验证列数至少为2
        if len(columns) < 2:
            raise ValueError(f"关联分析至少需要2列,当前只有{len(columns)}列")
        
        # 确保所有列名都是字符串
        columns = [str(col) for col in columns]
        
        # 验证列名不重复
        if len(columns) != len(set(columns)):
            duplicates = [col for col in columns if columns.count(col) > 1]
            raise ValueError(f"列名不能重复,发现重复的列名: {set(duplicates)}")
        
        validated['columns'] = columns
        
        # 验证analysis_mode
        analysis_mode = parameters.get('analysis_mode')
        if not analysis_mode:
            # 根据列数自动推断
            if len(columns) == 2:
                analysis_mode = 'bivariate'
            elif len(columns) >= 3:
                analysis_mode = 'pairwise'
            logger.info(f"未指定analysis_mode,根据列数自动推断为: {analysis_mode}")
        
        # 验证analysis_mode是有效值
        valid_modes = ['bivariate', 'pairwise', 'multivariate']
        if analysis_mode not in valid_modes:
            raise ValueError(f"无效的analysis_mode: {analysis_mode},有效值为: {valid_modes}")
        
        # 根据analysis_mode验证列数要求
        if analysis_mode == 'bivariate':
            if len(columns) != 2:
                raise ValueError(f"bivariate模式要求恰好2列,当前有{len(columns)}列")
        elif analysis_mode in ['pairwise', 'multivariate']:
            if len(columns) < 3:
                raise ValueError(f"{analysis_mode}模式至少需要3列,当前只有{len(columns)}列")
        
        validated['analysis_mode'] = analysis_mode
        

        
        # 保留旧格式字段(向后兼容)
        if len(columns) == 2:
            validated['column1'] = columns[0]
            validated['column2'] = columns[1]
        
        logger.info(
            f"关联分析参数验证通过: columns={columns}, "
            f"mode={analysis_mode}"
        )
        
        return validated
    
    def get_last_query_db_result(self) -> Dict[str, Any]:
        """获取最后一次query_db的结果"""
        return getattr(self, '_last_query_db_result', {})
