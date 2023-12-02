from flask import Flask, request, jsonify
from neo4j import GraphDatabase
from uuid import uuid4

app = Flask(__name__)

uri = "bolt://localhost:7687"
driver = GraphDatabase.driver(uri, auth=("neo4j", "test1234"))


def create_employee(tx, name):
    tx.run("CREATE (:Employee {id: $id, name: $name})", id=uuid4(), name=name)


def create_department(tx, name):
    tx.run("CREATE (:Department {id=$id, name: $name})", id=uuid4(), name=name)


def create_relationship_works_in(tx, e_name, d_name):
    tx.run(
        """
    MATCH (e:Employee {name: $e_name})
    MATCH (d:Department {name: $d_name})
    MERGE (e)-[:WORKS_IN]->(d)
    """,
        e_name=e_name,
        d_name=d_name,
    )


def create_relationship_manages(tx, e_name, d_name):
    tx.run(
        """
    MATCH (e:Employee {name: $e_name})
    MATCH (d:Department {name: $d_name})
    MERGE (e)-[:MANAGES]->(d)
    """,
        e_name=e_name,
        d_name=d_name,
    )


def get_employees(tx, name=None, order=None, department=None, position=None):
    query = "MATCH (e:Employee)-[r]->(d:Department)"
    conditions = []
    if name:
        conditions.append("e.name CONTAINS $name")
    if department:
        conditions.append("d.name CONTAINS $department")
    if position:
        conditions.append("r.type CONTAINS $position")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " RETURN e.name, d, r"
    if order:
        query += " ORDER BY e.name " + order
    result = tx.run(query, name=name, order=order, department=department)
    return [
        {
            "name": record["e.name"],
            "position": record["r"].type,
            "department": record["d"]["name"],
        }
        for record in result
    ]


def update_employee(tx, id, name=None, position=None, department=None):
    if name:
        tx.run(
            "MATCH (e:Employee) WHERE e.id = $id SET e.name = $name",
            id=id,
            name=name,
        )
    if position:
        tx.run(
            """
        MATCH (e:Employee)-[r]->(d:Department) WHERE e.id = $id
        DELETE r
        CREATE (e)-[:$position]->(d)
        """,
            id=id,
            position=position,
        )
    if department:
        tx.run(
            """
        MATCH (e:Employee)-[r]->(d:Department) WHERE e.id = $id
        DELETE r
        MATCH (d2:Department {name: $department})
        CREATE (e)-[:$position]->(d2)
        """,
            id=id,
            position=position,
            department=department,
        )


def delete_employee(tx, id):
    # Sprawdź, czy pracownik jest menadżerem jakiegoś departamentu
    result = tx.run(
        """
    MATCH (e:Employee)-[:MANAGES]->(d:Department) WHERE e.id = $id
    RETURN d
    """,
        id=id,
    )
    record = result.single()
    if record:
        # Jeśli tak, znajdź innego pracownika z tego samego departamentu
        result = tx.run(
            """
        MATCH (e2:Employee)-[:WORKS_IN]->(d:Department) WHERE d.id = $d AND e2.id <> $id
        RETURN e2
        """,
            id=id,
            d=record["d"],
        )
        record2 = result.single()
        if record2:
            # Jeśli istnieje, ustaw go jako nowego menadżera
            tx.run(
                """
            MATCH (e2:Employee) WHERE e2.id = $e2
            CREATE (e2)-[:MANAGES]->(d)
            """,
                e2=record2["e2"],
                d=record["d"],
            )
        else:
            # Jeśli nie, usuń departament
            tx.run("MATCH (d:Department) WHERE d.id = $d DELETE d", d=record["d"])
    # Usuń pracownika
    tx.run("MATCH (e:Employee) WHERE e.id = $id DELETE e", id=id)


def get_departments(tx, name=None, order=None):
    query = "MATCH (d:Department)"
    if name:
        query += " WHERE d.name CONTAINS $name"
    query += " RETURN d.name"
    if order:
        query += " ORDER BY d.name " + order
    result = tx.run(query, name=name, order=order)
    return [record["d.name"] for record in result]


def get_subordinates(tx, id):
    result = tx.run(
        """
    MATCH (e:Employee)-[:MANAGES]->()<-[:WORKS_IN]-(e2:Employee) WHERE e.id = $id
    RETURN e2.name
    """,
        id=id,
    )
    return [record["e2.name"] for record in result]


def department_employees(tx, id):
    result = tx.run(
        """
    MATCH (d:Department)<-[:WORKS_IN]-(e:Employee) WHERE d.id = $id
    RETURN e.name
    """,
        id=id,
    )
    return [record["e.name"] for record in result]


def employee_department_count(tx, id):
    result = tx.run(
        """
    MATCH (e:Employee)-[:WORKS_IN]->(d:Department) WHERE id(e) = $id
    RETURN d.name AS department_name, size((d)<-[:WORKS_IN]-()) AS num_employees
    """,
        id=id,
    )
    record = result.single()
    if record:
        return {
            "department_name": record["department_name"],
            "num_employees": record["num_employees"],
        }


def create_employees_and_departments(tx):
    employees = [
        "John Doe",
        "Jane Smith",
        "Robert Johnson",
        "Michael Williams",
        "Sarah Brown",
        "James Jones",
        "Patricia Miller",
        "Richard Davis",
        "Linda Garcia",
        "Charles Rodriguez",
        "Elizabeth Martinez",
        "Thomas Wilson",
        "Jennifer Moore",
        "Joseph Taylor",
        "Susan Anderson",
        "William Thomas",
        "Jessica Jackson",
        "David White",
        "Mary Harris",
        "Kenneth Martin",
    ]
    departments = ["HR", "Sales", "IT", "Marketing"]

    for name in employees:
        tx.run(
            "CREATE (:Employee { id: $id, name: $name })", name=name, id=str(uuid4())
        )

    for name in departments:
        tx.run(
            "CREATE (:Department { id: $id, name: $name })", name=name, id=str(uuid4())
        )

    for i, name in enumerate(employees[4:]):
        d_name = departments[i % len(departments)]
        tx.run(
            """
        MATCH(e: Employee {name: $name})
        MATCH(d: Department {name: $d_name})
        MERGE(e)-[:WORKS_IN] -> (d)
        """,
            name=name,
            d_name=d_name,
        )

    for i, name in enumerate(employees[:5]):
        d_name = departments[i % len(departments)]
        tx.run(
            """
        MATCH(e: Employee {name: $name})
        MATCH(d: Department {name: $d_name})
        MERGE(e)-[:MANAGES] -> (d)
        """,
            name=name,
            d_name=d_name,
        )


@app.route("/employees", methods=["POST"])
def add_employee():
    if request.json is None or not request.json["name"]:
        return jsonify({"message": "Request body is empty or wrong data"}), 400
    name = request.json["name"]
    with driver.session() as session:
        employees = session.read_transaction(get_employees, name=name)
        if employees:
            return jsonify({"message": "Employee already exists"}), 400
        session.write_transaction(create_employee, name)
    return jsonify({"message": "Employee created successfully"}), 201


@app.route("/department", methods=["POST"])
def add_department():
    if request.json is None:
        return jsonify({"message": "Request body is empty"}), 400
    name = request.json["name"]
    with driver.session() as session:
        session.write_transaction(create_department, name)
    return jsonify({"message": "Department created successfully"}), 201


@app.route("/relationship/works-in", methods=["POST"])
def add_relationship_works_in():
    if request.json is None:
        return jsonify({"message": "Request body is empty"}), 400
    e_name = request.json["employee"]
    d_name = request.json["department"]
    with driver.session() as session:
        session.write_transaction(create_relationship_works_in, e_name, d_name)
    return jsonify({"message": "Relationship created successfully"}), 201


@app.route("/relationship/manages", methods=["POST"])
def add_relationship_manages():
    if request.json is None:
        return jsonify({"message": "No data provided"}), 400
    e_name = request.json["employee"]
    d_name = request.json["department"]
    with driver.session() as session:
        session.write_transaction(create_relationship_manages, e_name, d_name)
    return jsonify({"message": "Relationship created successfully"}), 201


@app.route("/employees", methods=["GET"])
def get_all_employees():
    name = request.args.get("name")
    order = request.args.get("order")
    department = request.args.get("department")
    with driver.session() as session:
        employees = session.read_transaction(get_employees, name, order, department)
    return jsonify(employees), 200


@app.route("/employees/<id>", methods=["PUT"])
def edit_employee(id):
    if request.json is None:
        return jsonify({"message": "No JSON data provided"}), 400
    name = request.json.get("name")
    position = request.json.get("position")
    department = request.json.get("department")
    with driver.session() as session:
        session.write_transaction(update_employee, id, name, position, department)
    return jsonify({"message": "Employee updated successfully"}), 200


@app.route("/employees/<id>", methods=["DELETE"])
def remove_employee(id):
    with driver.session() as session:
        session.write_transaction(delete_employee, id)
    return jsonify({"message": "Employee deleted successfully"}), 200


@app.route("/employees/<id>/subordinates", methods=["GET"])
def get_employee_subordinates(id):
    with driver.session() as session:
        subordinates = session.read_transaction(get_subordinates, id)
    return jsonify(subordinates), 200


@app.route("/departments", methods=["GET"])
def get_all_departments():
    name = request.args.get("name")
    order = request.args.get("order")
    with driver.session() as session:
        departments = session.read_transaction(get_departments, name, order)
    return jsonify(departments), 200


@app.route("/departments/<int:id>/employees", methods=["GET"])
def get_department_employees(id):
    with driver.session() as session:
        employees = session.read_transaction(department_employees, id)
    return jsonify(employees), 200


@app.route("/employees/<int:id>/department", methods=["GET"])
def get_employee_department(id):
    with driver.session() as session:
        department = session.read_transaction(employee_department_count, id)
    if department:
        return jsonify(department), 200
    else:
        return jsonify(
            {"message": "Employee not found or does not work in a department"}
        ), 404


if __name__ == "__main__":
    # with driver.session() as session:
    #     session.execute_write(create_employees_and_departments)
    app.run(debug=True)

