from ortools.sat.python import cp_model

def generate_schedule(data: dict):
    model = cp_model.CpModel()
    year = data.get("year", "FY")
    divisions_data = data.get("divisions", [])
    div_names = [div["name"] for div in divisions_data]
    
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    # FIX 1: Erase 17:00 from existence. The day now STRICTLY ends at 17:00 (5 PM).
    hours = list(range(8, 17)) 
    
    # 1. DATA EXTRACTION
    theory_info = {} 
    lab_info = {}    
    all_facs = set()
    all_rooms = set()

    for div in divisions_data:
        d_name = div["name"]
        d_room = div.get("theory_room", "Unassigned")
        
        for sub in div.get("subjects", []):
            s_name = sub["name"]
            
            # Theory
            t_fac = sub.get("theory_faculty", "Unassigned")
            t_req = sub.get("theory_lectures_per_week", 3)
            theory_info[(d_name, s_name)] = {"fac": t_fac, "room": d_room, "req": t_req}
            all_facs.add(t_fac)
            all_rooms.add(d_room)
            
            # Labs
            if sub.get("has_lab") and "batches" in sub:
                for batch in sub["batches"]:
                    b_name = batch["name"]
                    l_fac = batch.get("faculty", "Unassigned")
                    l_room = batch.get("lab_room", "Unassigned")
                    lab_info[(d_name, s_name, b_name)] = {"fac": l_fac, "room": l_room}
                    all_facs.add(l_fac)
                    all_rooms.add(l_room)

    all_facs.discard("Unassigned")
    all_facs.discard("")
    all_rooms.discard("Unassigned")
    all_rooms.discard("")

    # 2. VARIABLE CREATION
    theory_vars = {}
    lab_start_vars = {}
    lab_active_vars = {}
    div_lab_active = {}
    break_vars = {}

    for d in div_names:
        for day in days:
            for h in hours:
                div_lab_active[(d, day, h)] = model.NewBoolVar(f"dla_{d}_{day}_{h}")
            for h in [12, 13, 14]:
                break_vars[(d, day, h)] = model.NewBoolVar(f"brk_{d}_{day}_{h}")

    for (d, s), info in theory_info.items():
        for day in days:
            for h in hours:
                theory_vars[(d, s, day, h)] = model.NewBoolVar(f"t_{d}_{s}_{day}_{h}")

    for (d, s, b), info in lab_info.items():
        for day in days:
            for h in hours:
                lab_active_vars[(d, s, b, day, h)] = model.NewBoolVar(f"la_{d}_{s}_{b}_{day}_{h}")
                if h < hours[-1]: 
                    lab_start_vars[(d, s, b, day, h)] = model.NewBoolVar(f"ls_{d}_{s}_{b}_{day}_{h}")

    # 3. CONSTRAINTS
    # A. Floating Breaks (Exactly 1 per day, intelligently placed)
    for d in div_names:
        for day in days:
            model.AddExactlyOne([break_vars[(d, day, h)] for h in [12, 13, 14]])

    # B. Theory Rules 
    for (d, s), info in theory_info.items():
        model.Add(sum(theory_vars[(d, s, day, h)] for day in days for h in hours) == info["req"])
        for day in days:
            model.Add(sum(theory_vars[(d, s, day, h)] for h in hours) <= 1)

    # C. Lab Rules (2-Hour Continuous)
    for (d, s, b), info in lab_info.items():
        model.Add(sum(lab_start_vars[(d, s, b, day, h)] for day in days for h in hours[:-1]) == 1)
        for day in days:
            for h in hours:
                terms = []
                if h < hours[-1]: terms.append(lab_start_vars[(d, s, b, day, h)])     
                if h > hours[0]: terms.append(lab_start_vars[(d, s, b, day, h-1)])   
                model.Add(lab_active_vars[(d, s, b, day, h)] == sum(terms))

    # C2. No two batches from the same division can have the same subject lab on the same day
    for d in div_names:
        for day in days:
            lab_subjects = set(s for (div, s, b) in lab_info.keys() if div == d)
            for s in lab_subjects:
                same_sub_starts = []
                for b in [batch for (div, sub, batch) in lab_info.keys() if div == d and sub == s]:
                    for h in hours[:-1]:
                        same_sub_starts.append(lab_start_vars[(d, s, b, day, h)])
                model.Add(sum(same_sub_starts) <= 1)

    # D. Division Lab Block Logic
    for d in div_names:
        for day in days:
            for h in hours:
                for (div, s, b) in lab_info.keys():
                    if div == d:
                        model.AddImplication(lab_active_vars[(d, s, b, day, h)], div_lab_active[(d, day, h)])
            model.Add(sum(div_lab_active[(d, day, h)] for h in hours) <= 2)

    # E. Mutual Exclusivity (No Clashes for Division/Batches)
    for d in div_names:
        for day in days:
            for h in hours:
                running_theories = [theory_vars[(div, s, day, h)] for (div, s) in theory_info.keys() if div == d]
                is_lab = div_lab_active[(d, day, h)]
                is_break = break_vars.get((d, day, h), 0)
                model.Add(sum(running_theories) + is_lab + is_break <= 1)

                batch_labs = {}
                for (div, s, b) in lab_info.keys():
                    if div == d: batch_labs.setdefault(b, []).append(lab_active_vars[(d, s, b, day, h)])
                for b, acts in batch_labs.items():
                    model.Add(sum(acts) <= 1)

    # F. Faculty & Room Clashes
    for day in days:
        for h in hours:
            for fac in all_facs:
                fac_active = []
                for (d, s), info in theory_info.items():
                    if info["fac"] == fac: fac_active.append(theory_vars[(d, s, day, h)])
                for (d, s, b), info in lab_info.items():
                    if info["fac"] == fac: fac_active.append(lab_active_vars[(d, s, b, day, h)])
                model.Add(sum(fac_active) <= 1)

            for room in all_rooms:
                room_active = []
                for (d, s), info in theory_info.items():
                    if info["room"] == room: room_active.append(theory_vars[(d, s, day, h)])
                for (d, s, b), info in lab_info.items():
                    if info["room"] == room: room_active.append(lab_active_vars[(d, s, b, day, h)])
                model.Add(sum(room_active) <= 1)

    # G. Work Hour Boundaries
    for d in div_names:
        for day in days:
            for h in hours:
                all_active_vars = [theory_vars[(div, s, day, h)] for (div, s) in theory_info.keys() if div == d]
                all_active_vars.append(div_lab_active[(d, day, h)])
                
                if year in ["SY", "TY"] and h < 10: model.Add(sum(all_active_vars) == 0)

    # H. FIX 2: Exponential Optimization (Kills the Gaps)
    penalty_terms = []
    for d in div_names:
        for day in days:
            for h in hours:
                # Exponential penalty: 4 PM is massively penalized compared to 3 PM
                # This mathematically forces the solver to slide everything to the morning!
                weight = 2 ** (h - 8) 
                
                for (div, s), info in theory_info.items():
                    if div == d: penalty_terms.append(theory_vars[(d, s, day, h)] * weight)
                for (div, s, b), info in lab_info.items():
                    if div == d: penalty_terms.append(lab_active_vars[(d, s, b, day, h)] * weight)
                    
    model.Minimize(sum(penalty_terms))

    # 4. SOLVE AND FORMAT
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 15.0 
    status = solver.Solve(model)
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        timetable_data = {}
        for d in div_names:
            timetable_data[d] = {}
            for day in days:
                timetable_data[d][day] = {}
                # Even though we solve up to 16, we output up to 17 so the frontend grid matches
                for h in range(8, 18):
                    if h >= 17:
                        timetable_data[d][day][str(h)] = "-"
                        continue
                        
                    is_break = False
                    for bh in [12, 13, 14]:
                        if bh == h and solver.Value(break_vars[(d, day, bh)]) == 1:
                            is_break = True
                            break
                    if is_break:
                        timetable_data[d][day][str(h)] = "<div style='color: #8b949e; letter-spacing: 2px; padding: 10px 0; font-weight: bold;'>BREAK</div>"
                        continue

                    contents = []
                    for (div, s), info in theory_info.items():
                        if div == d and solver.Value(theory_vars[(div, s, day, h)]) == 1:
                            contents.append(f"<strong>{s}</strong><br>{info['fac']}<br><small>{info['room']}</small>")

                    lab_contents = []
                    for (div, s, b), info in lab_info.items():
                        if div == d and solver.Value(lab_active_vars[(div, s, b, day, h)]) == 1:
                            lab_contents.append(f"<strong>{s}-LAB ({b})</strong><br>{info['fac']}<br><small>{info['room']}</small>")

                    if lab_contents:
                        contents.append("<hr style='margin:8px 0; border:none; border-top:1px dashed rgba(255,255,255,0.15);'>".join(lab_contents))

                    if contents: timetable_data[d][day][str(h)] = "".join(contents)
                    else: timetable_data[d][day][str(h)] = "-"
                        
        return {"status": "success", "data": timetable_data}
    
    return {"status": "error", "message": "Clash detected! Impossible to schedule rules."}